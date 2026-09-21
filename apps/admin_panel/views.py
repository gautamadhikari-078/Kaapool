import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, View, ListView, DetailView
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse

from apps.rides.models import Ride, Vehicle
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.notifications.models import Notification
from apps.admin_panel.models import (
    VerificationRecord, Complaint, AuditLog, SystemSetting, ContactInquiry
)
from apps.admin_panel.permissions import AdminRequiredMixin, PermissionRequiredMixin, log_audit_action
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from apps.core.email_service import EmailService

User = get_user_model()


class AdminLoginView(View):
    """Secure Admin Login view."""
    template_name = 'admin_panel/login.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, 'is_admin', False):
            return redirect('admin_panel:dashboard')
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username_or_email or not password:
            messages.error(request, 'Please provide both username/email and password.')
            return render(request, self.template_name)

        # Authenticate by username or email (case-insensitive)
        candidate = User.objects.filter(
            Q(username__iexact=username_or_email) | Q(email__iexact=username_or_email)
        ).first()

        user = None
        if candidate:
            user = authenticate(request, username=candidate.username, password=password)
        if not user:
            user = authenticate(request, username=username_or_email, password=password)

        if user:
            if getattr(user, 'is_blocked', False):
                messages.error(request, 'This account is currently blocked.')
                return render(request, self.template_name)

            if not getattr(user, 'is_admin', False):
                messages.error(request, 'Access denied. Account does not have admin permissions.')
                return render(request, self.template_name)

            login(request, user)
            log_audit_action(user, 'ADMIN_LOGIN', target_type='User', target_id=user.id, request=request)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            next_url = request.GET.get('next') or reverse('admin_panel:dashboard')
            return redirect(next_url)

        messages.error(request, 'Invalid credentials provided.')
        return render(request, self.template_name)


class AdminLogoutView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            log_audit_action(request.user, 'ADMIN_LOGOUT', target_type='User', target_id=request.user.id, request=request)
            logout(request)
        messages.info(request, 'You have been logged out of the Admin Panel.')
        return redirect('admin_panel:login')


class AdminPasswordResetRequestView(View):
    """Admin Password Reset Request View - sends reset link directly to linked admin email."""
    template_name = 'admin_panel/password_reset.html'
    ADMIN_LINKED_EMAIL = 'gautamadhikari071@gmail.com'

    def get_admin_user(self):
        user = User.objects.filter(email__iexact=self.ADMIN_LINKED_EMAIL).first()
        if not user:
            user = User.objects.filter(username='admin').first()
        if not user:
            user = User.objects.filter(is_superuser=True).first()
        return user

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and getattr(request.user, 'is_admin', False):
            return redirect('admin_panel:dashboard')
        return render(request, self.template_name, {
            'linked_email': self.ADMIN_LINKED_EMAIL
        })

    def post(self, request, *args, **kwargs):
        user = self.get_admin_user()
        reset_url = None

        if user:
            user.email = self.ADMIN_LINKED_EMAIL
            user.is_superuser = True
            user.is_staff = True
            user.role = 'super_admin'
            user.email_verified = True
            user.save()

            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            relative_url = reverse('admin_panel:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
            reset_url = request.build_absolute_uri(relative_url)
            # Ensure HTTPS for public hosting (Render)
            if 'onrender.com' in reset_url and reset_url.startswith('http://'):
                reset_url = reset_url.replace('http://', 'https://', 1)

            try:
                EmailService.send_password_reset_email(user, reset_url, async_send=False)
                log_audit_action(user, 'ADMIN_PASSWORD_RESET_REQUESTED', target_type='User', target_id=user.id, request=request)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send admin password reset email: {e}")

        return render(request, 'admin_panel/password_reset_done.html', {
            'email': self.ADMIN_LINKED_EMAIL,
            'reset_url': reset_url,
        })


class AdminPasswordResetConfirmView(View):
    """Admin Password Reset Confirmation View - verifies token and sets new password."""
    template_name = 'admin_panel/password_reset_confirm.html'

    def get_user_and_valid_token(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.filter(pk=uid).first()
            if user and getattr(user, 'is_admin', False) and not getattr(user, 'is_blocked', False):
                if default_token_generator.check_token(user, token):
                    return user, True
        except (TypeError, ValueError, OverflowError):
            pass
        return None, False

    def get(self, request, uidb64, token, *args, **kwargs):
        user, is_valid = self.get_user_and_valid_token(uidb64, token)
        if not is_valid:
            return render(request, 'admin_panel/password_reset_invalid.html')
        return render(request, self.template_name, {'uidb64': uidb64, 'token': token, 'target_user': user})

    def post(self, request, uidb64, token, *args, **kwargs):
        user, is_valid = self.get_user_and_valid_token(uidb64, token)
        if not is_valid:
            return render(request, 'admin_panel/password_reset_invalid.html')

        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, self.template_name, {'uidb64': uidb64, 'token': token, 'target_user': user})

        if password != confirm_password:
            messages.error(request, "Passwords do not match. Please try again.")
            return render(request, self.template_name, {'uidb64': uidb64, 'token': token, 'target_user': user})

        user.set_password(password)
        user.save()

        # Keep admin user and owner account in sync
        if user.username != 'admin':
            admin_user = User.objects.filter(username='admin').first()
            if admin_user:
                admin_user.set_password(password)
                admin_user.save()
        else:
            owner_user = User.objects.filter(email='gautamadhikari071@gmail.com').first()
            if owner_user and owner_user != user:
                owner_user.set_password(password)
                owner_user.save()

        log_audit_action(user, 'ADMIN_PASSWORD_RESET_COMPLETED', target_type='User', target_id=user.id, request=request)
        messages.success(request, "Your admin password has been updated successfully! You can now sign in with your new password.")
        return redirect('admin_panel:login')


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Clean, real-time KPI overview dashboard."""
    template_name = 'admin_panel/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Real backend KPI stats
        total_users = User.objects.count()
        verified_users = User.objects.filter(is_verified_driver=True).count()
        pending_verifications = VerificationRecord.objects.filter(status='IN_PROGRESS').count()
        
        total_drivers = User.objects.filter(offered_rides__isnull=False).distinct().count()
        active_drivers = User.objects.filter(offered_rides__status='active').distinct().count()
        
        active_rides = Ride.objects.filter(status='active').count()
        upcoming_rides = Ride.objects.filter(status='active', departure_datetime__gte=timezone.now()).count()
        completed_rides = Ride.objects.filter(status='completed').count()
        cancelled_rides = Ride.objects.filter(status='cancelled').count()
        
        total_bookings = Booking.objects.count()
        open_complaints = Complaint.objects.filter(status__in=['OPEN', 'UNDER_REVIEW', 'IN_PROGRESS']).count()

        # Payment summary
        payment_stats = Payment.objects.aggregate(
            total_amount=Sum('amount'),
            completed_count=Count('id', filter=Q(status='completed'))
        )

        # Recent activities
        recent_users = User.objects.order_by('-date_joined')[:5]
        recent_rides = Ride.objects.select_related('driver').order_by('-created_at')[:5]
        recent_bookings = Booking.objects.select_related('passenger', 'ride').order_by('-created_at')[:5]
        recent_verifications = VerificationRecord.objects.select_related('user').order_by('-updated_at')[:5]
        recent_audit_logs = AuditLog.objects.select_related('admin').order_by('-created_at')[:6]

        context.update({
            'total_users': total_users,
            'verified_users': verified_users,
            'pending_verifications': pending_verifications,
            'total_drivers': total_drivers,
            'active_drivers': active_drivers,
            'active_rides': active_rides,
            'upcoming_rides': upcoming_rides,
            'completed_rides': completed_rides,
            'cancelled_rides': cancelled_rides,
            'total_bookings': total_bookings,
            'open_complaints': open_complaints,
            'total_payments': payment_stats['total_amount'] or 0,
            'recent_users': recent_users,
            'recent_rides': recent_rides,
            'recent_bookings': recent_bookings,
            'recent_verifications': recent_verifications,
            'recent_audit_logs': recent_audit_logs,
            'active_section': 'dashboard'
        })
        return context


# --- USER MANAGEMENT ---

class AdminUserListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/users/list.html'
    model = User
    context_object_name = 'users'
    paginate_by = 15

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        search = self.request.GET.get('search', '').strip()
        role_filter = self.request.GET.get('role', '').strip()
        status_filter = self.request.GET.get('status', '').strip()

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        if role_filter:
            if role_filter == 'driver':
                queryset = queryset.filter(offered_rides__isnull=False).distinct()
            elif role_filter == 'passenger':
                queryset = queryset.filter(ride_bookings__isnull=False).distinct()
            else:
                queryset = queryset.filter(role=role_filter)
        if status_filter:
            if status_filter == 'blocked':
                queryset = queryset.filter(is_blocked=True)
            elif status_filter == 'active':
                queryset = queryset.filter(is_blocked=False, is_active=True)
            elif status_filter == 'verified':
                queryset = queryset.filter(is_verified_driver=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['role_filter'] = self.request.GET.get('role', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['active_section'] = 'users'
        return context


class AdminUserDetailView(AdminRequiredMixin, DetailView):
    template_name = 'admin_panel/users/detail.html'
    model = User
    context_object_name = 'target_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        context['user_rides'] = Ride.objects.filter(driver=target).order_by('-created_at')
        context['user_bookings'] = Booking.objects.filter(passenger=target).select_related('ride').order_by('-created_at')
        context['user_vehicles'] = Vehicle.objects.filter(user=target)
        context['user_verifications'] = VerificationRecord.objects.filter(user=target).order_by('-created_at')
        context['user_complaints'] = Complaint.objects.filter(user=target).order_by('-created_at')
        context['active_section'] = 'users'
        return context


class AdminUserActionView(PermissionRequiredMixin, View):
    required_permission = 'users.block'

    def post(self, request, pk, *args, **kwargs):
        target_user = get_object_or_404(User, pk=pk)
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()

        if action == 'block':
            target_user.is_blocked = True
            target_user.block_reason = reason or 'Blocked by administrator'
            target_user.save()
            log_audit_action(request.user, 'BLOCK_USER', target_type='User', target_id=target_user.id, details={'reason': reason}, request=request)
            messages.success(request, f"User {target_user} has been blocked.")
        elif action == 'unblock':
            target_user.is_blocked = False
            target_user.block_reason = ''
            target_user.save()
            log_audit_action(request.user, 'UNBLOCK_USER', target_type='User', target_id=target_user.id, request=request)
            messages.success(request, f"User {target_user} has been unblocked.")
        elif action == 'toggle_driver_verify':
            target_user.is_verified_driver = not target_user.is_verified_driver
            target_user.save()
            log_audit_action(request.user, 'MANUAL_VERIFY_DRIVER', target_type='User', target_id=target_user.id, details={'verified': target_user.is_verified_driver}, request=request)
            messages.success(request, f"Driver verification status updated for {target_user}.")

        return redirect('admin_panel:user_detail', pk=target_user.pk)


# --- VERIFICATION MANAGEMENT ---

class AdminVerificationListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/verifications/list.html'
    model = VerificationRecord
    context_object_name = 'verifications'
    paginate_by = 15

    def get_queryset(self):
        queryset = VerificationRecord.objects.select_related('user').order_by('-updated_at')
        status_filter = self.request.GET.get('status', '').strip()
        search = self.request.GET.get('search', '').strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(session_id__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        context['active_section'] = 'verifications'
        return context


class AdminVerificationDetailView(AdminRequiredMixin, DetailView):
    template_name = 'admin_panel/verifications/detail.html'
    model = VerificationRecord
    context_object_name = 'verification'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'verifications'
        return context


class AdminVerificationActionView(PermissionRequiredMixin, View):
    required_permission = 'verification.review'

    def post(self, request, pk, *args, **kwargs):
        verification = get_object_or_404(VerificationRecord, pk=pk)
        new_status = request.POST.get('status')
        reason = request.POST.get('reason', '').strip()

        if new_status in ['APPROVED', 'DECLINED', 'RESUBMISSION_REQUESTED']:
            verification.status = new_status
            verification.decision_reason = reason
            verification.save()

            if new_status == 'APPROVED':
                verification.user.is_verified_driver = True
                verification.user.save()
            elif new_status == 'DECLINED':
                verification.user.is_verified_driver = False
                verification.user.save()

            log_audit_action(
                request.user,
                'REVIEW_VERIFICATION',
                target_type='VerificationRecord',
                target_id=verification.id,
                details={'new_status': new_status, 'reason': reason},
                request=request
            )
            messages.success(request, f"Verification #{verification.id} updated to {new_status}.")

        return redirect('admin_panel:verification_detail', pk=verification.pk)


# --- DRIVER & VEHICLE MANAGEMENT ---

class AdminDriverListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/drivers/list.html'
    model = User
    context_object_name = 'drivers'
    paginate_by = 15

    def get_queryset(self):
        return User.objects.filter(offered_rides__isnull=False).distinct().annotate(
            total_rides_count=Count('offered_rides')
        ).order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'drivers'
        return context


class AdminVehicleListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/vehicles/list.html'
    model = Vehicle
    context_object_name = 'vehicles'
    paginate_by = 15

    def get_queryset(self):
        return Vehicle.objects.select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'vehicles'
        return context


# --- RIDE & BOOKING MANAGEMENT ---

class AdminRideListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/rides/list.html'
    model = Ride
    context_object_name = 'rides'
    paginate_by = 15

    def get_queryset(self):
        queryset = Ride.objects.select_related('driver').order_by('-departure_datetime')
        status_filter = self.request.GET.get('status', '').strip()
        search = self.request.GET.get('search', '').strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(
                Q(origin__icontains=search) |
                Q(destination__icontains=search) |
                Q(driver__username__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        context['active_section'] = 'rides'
        return context


class AdminRideDetailView(AdminRequiredMixin, DetailView):
    template_name = 'admin_panel/rides/detail.html'
    model = Ride
    context_object_name = 'ride'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ride_bookings'] = Booking.objects.filter(ride=self.object).select_related('passenger')
        context['active_section'] = 'rides'
        return context


class AdminRideCancelView(PermissionRequiredMixin, View):
    required_permission = 'rides.cancel'

    def post(self, request, pk, *args, **kwargs):
        ride = get_object_or_404(Ride, pk=pk)
        reason = request.POST.get('reason', 'Cancelled by Super Admin')

        ride.status = 'cancelled'
        ride.save()

        # Update associated bookings
        Booking.objects.filter(ride=ride, status__in=['pending', 'confirmed']).update(
            status='cancelled',
            cancellation_reason='Ride cancelled by system administrator',
            cancellation_comment=reason
        )

        log_audit_action(request.user, 'CANCEL_RIDE', target_type='Ride', target_id=ride.id, details={'reason': reason}, request=request)
        messages.success(request, f"Ride #{ride.id} has been cancelled successfully.")
        return redirect('admin_panel:ride_detail', pk=ride.pk)


class AdminBookingListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/bookings/list.html'
    model = Booking
    context_object_name = 'bookings'
    paginate_by = 15

    def get_queryset(self):
        return Booking.objects.select_related('passenger', 'ride', 'ride__driver').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'bookings'
        return context


class AdminBookingDetailView(AdminRequiredMixin, DetailView):
    template_name = 'admin_panel/bookings/detail.html'
    model = Booking
    context_object_name = 'booking'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'bookings'
        return context


# --- PAYMENT MANAGEMENT ---

class AdminPaymentListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/payments/list.html'
    model = Payment
    context_object_name = 'payments'
    paginate_by = 15

    def get_queryset(self):
        return Payment.objects.select_related('user', 'booking').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'payments'
        return context


# --- COMPLAINT MANAGEMENT ---

class AdminComplaintListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/complaints/list.html'
    model = Complaint
    context_object_name = 'complaints'
    paginate_by = 15

    def get_queryset(self):
        queryset = Complaint.objects.select_related('user', 'assigned_admin').order_by('-created_at')
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['active_section'] = 'complaints'
        return context


class AdminComplaintDetailView(AdminRequiredMixin, DetailView):
    template_name = 'admin_panel/complaints/detail.html'
    model = Complaint
    context_object_name = 'complaint'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_users'] = User.objects.filter(
            Q(is_superuser=True) | Q(role__icontains='admin')
        )
        context['active_section'] = 'complaints'
        return context


class AdminComplaintUpdateView(PermissionRequiredMixin, View):
    required_permission = 'complaints.manage'

    def post(self, request, pk, *args, **kwargs):
        complaint = get_object_or_404(Complaint, pk=pk)
        new_status = request.POST.get('status')
        assigned_to_id = request.POST.get('assigned_admin')
        notes = request.POST.get('internal_notes', '').strip()

        if new_status:
            complaint.status = new_status
        if assigned_to_id:
            complaint.assigned_admin = User.objects.filter(id=assigned_to_id).first()
        if notes:
            complaint.internal_notes = notes

        complaint.save()
        log_audit_action(
            request.user,
            'UPDATE_COMPLAINT',
            target_type='Complaint',
            target_id=complaint.id,
            details={'status': new_status, 'assigned_admin': assigned_to_id},
            request=request
        )
        messages.success(request, f"Complaint #{complaint.id} updated successfully.")
        return redirect('admin_panel:complaint_detail', pk=complaint.pk)


# --- CONTACT INQUIRY MANAGEMENT ---

class AdminContactInquiryListView(AdminRequiredMixin, ListView):
    template_name = 'admin_panel/contact_inquiries/list.html'
    model = ContactInquiry
    context_object_name = 'inquiries'
    paginate_by = 15

    def get_queryset(self):
        queryset = ContactInquiry.objects.all().order_by('-created_at')
        status_filter = self.request.GET.get('status', '').strip()
        valid_filter = self.request.GET.get('valid', '').strip()
        search = self.request.GET.get('search', '').strip()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if valid_filter == 'true':
            queryset = queryset.filter(is_email_valid=True)
        elif valid_filter == 'false':
            queryset = queryset.filter(is_email_valid=False)

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(subject__icontains=search) |
                Q(message__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['valid_filter'] = self.request.GET.get('valid', '')
        context['search'] = self.request.GET.get('search', '')
        context['active_section'] = 'contact_inquiries'
        return context


class AdminContactInquiryReplyView(PermissionRequiredMixin, View):
    required_permission = 'complaints.manage'

    def post(self, request, pk, *args, **kwargs):
        from apps.admin_panel.models import ContactInquiry
        from apps.core.email_service import EmailService
        from django.utils import timezone

        inquiry = get_object_or_404(ContactInquiry, pk=pk)
        reply_message = request.POST.get('reply_message', '').strip()

        if not reply_message:
            messages.error(request, "Reply message cannot be empty.")
            return redirect('admin_panel:contact_inquiry_list')

        if not inquiry.is_email_valid:
            messages.error(request, f"Cannot send email to '{inquiry.email}' as it is marked as INVALID_EMAIL.")
            return redirect('admin_panel:contact_inquiry_list')

        try:
            html = EmailService._build_html_template(
                title=f"Re: {inquiry.subject}",
                body_content=f"""
                <p>Hi <strong>{inquiry.name}</strong>,</p>
                <p>{reply_message}</p>
                <div style="background-color: #f8fafc; border-left: 4px solid #f89516; padding: 12px 16px; margin: 15px 0; font-size: 13px; color: #64748b;">
                    <strong>Your Original Inquiry:</strong><br>
                    "{inquiry.message}"
                </div>
                """,
                badge_text="Support Response"
            )
            EmailService.send_email(
                subject=f"Re: {inquiry.subject}",
                recipient_list=inquiry.email,
                html_content=html,
                notification_type='admin_reply'
            )
            inquiry.status = 'RESPONDED'
            inquiry.admin_notes = f"Replied on {timezone.now().strftime('%Y-%m-%d %H:%M')}: {reply_message}"
            inquiry.admin_replied_at = timezone.now()
            inquiry.save()

            messages.success(request, f"Email reply successfully sent to {inquiry.email}.")
        except Exception as e:
            messages.error(request, f"Error sending email reply: {e}")

        return redirect('admin_panel:contact_inquiry_list')


class AdminContactInquiryDeleteView(PermissionRequiredMixin, View):
    required_permission = 'complaints.manage'

    def post(self, request, pk, *args, **kwargs):
        from apps.admin_panel.models import ContactInquiry
        inquiry = get_object_or_404(ContactInquiry, pk=pk)
        email_str = inquiry.email
        inquiry.delete()
        log_audit_action(request.user, 'DELETE_CONTACT_INQUIRY', target_type='ContactInquiry', target_id=pk, details={'email': email_str}, request=request)
        messages.success(request, f"Contact inquiry from '{email_str}' deleted from database.")
        return redirect('admin_panel:contact_inquiry_list')


# --- ADMIN USERS & ROLES (SUPER ADMIN ONLY) ---

class AdminAdminsView(PermissionRequiredMixin, View):
    required_permission = 'admin.manage'
    template_name = 'admin_panel/admins/list.html'

    def get(self, request, *args, **kwargs):
        admins = User.objects.filter(
            Q(is_superuser=True) | Q(role__in=['super_admin', 'operations_admin', 'verification_admin', 'support_admin', 'content_admin', 'finance_admin'])
        ).order_by('-date_joined')

        return render(request, self.template_name, {
            'admins': admins,
            'role_choices': User.ROLE_CHOICES,
            'active_section': 'admins'
        })

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')

        target_user = get_object_or_404(User, pk=user_id)
        target_user.role = new_role
        target_user.is_staff = new_role != 'user'
        target_user.save()

        log_audit_action(request.user, 'CHANGE_ADMIN_ROLE', target_type='User', target_id=target_user.id, details={'new_role': new_role}, request=request)
        messages.success(request, f"Role updated to {new_role} for {target_user}.")
        return redirect('admin_panel:admins_list')


# --- SYSTEM SETTINGS & AUDIT LOGS ---

class AdminSettingsView(PermissionRequiredMixin, View):
    required_permission = 'admin.manage'
    template_name = 'admin_panel/settings/index.html'

    def get(self, request, *args, **kwargs):
        settings_objs = SystemSetting.objects.all()
        return render(request, self.template_name, {
            'settings': settings_objs,
            'active_section': 'settings'
        })

    def post(self, request, *args, **kwargs):
        key = request.POST.get('key', '').strip()
        val_str = request.POST.get('value', '').strip()

        if key:
            obj, _ = SystemSetting.objects.get_or_create(key=key)
            try:
                obj.value = json.loads(val_str)
            except Exception:
                obj.value = {'raw': val_str}
            obj.save()
            log_audit_action(request.user, 'UPDATE_SYSTEM_SETTING', target_type='SystemSetting', target_id=key, request=request)
            messages.success(request, f"Setting '{key}' updated.")

        return redirect('admin_panel:settings')


class AdminAuditLogView(PermissionRequiredMixin, ListView):
    required_permission = 'audit.view'
    template_name = 'admin_panel/audit_logs/list.html'
    model = AuditLog
    context_object_name = 'logs'
    paginate_by = 25

    def get_queryset(self):
        return AuditLog.objects.select_related('admin').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_section'] = 'audit_logs'
        return context


# --- FULL CRUD ACTION VIEWS ---

class AdminUserCreateView(PermissionRequiredMixin, View):
    required_permission = 'users.edit'

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'user')

        if not username or not password:
            messages.error(request, 'Username and Password are required.')
            return redirect('admin_panel:user_list')

        if User.objects.filter(username=username).exists():
            messages.error(request, f"User with username '{username}' already exists.")
            return redirect('admin_panel:user_list')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=role,
            is_staff=role != 'user'
        )
        log_audit_action(request.user, 'CREATE_USER', target_type='User', target_id=user.id, request=request)
        messages.success(request, f"User '{user.username}' created successfully.")
        return redirect('admin_panel:user_list')


class AdminUserEditView(PermissionRequiredMixin, View):
    required_permission = 'users.edit'

    def post(self, request, pk, *args, **kwargs):
        target_user = get_object_or_404(User, pk=pk)
        target_user.first_name = request.POST.get('first_name', '').strip()
        target_user.last_name = request.POST.get('last_name', '').strip()
        target_user.email = request.POST.get('email', '').strip()
        target_user.phone_number = request.POST.get('phone_number', '').strip()
        target_user.role = request.POST.get('role', target_user.role)
        target_user.is_staff = target_user.role != 'user'

        new_password = request.POST.get('password', '').strip()
        if new_password:
            target_user.set_password(new_password)

        target_user.save()
        log_audit_action(request.user, 'UPDATE_USER', target_type='User', target_id=target_user.id, request=request)
        messages.success(request, f"User '{target_user.username}' updated successfully.")
        return redirect('admin_panel:user_detail', pk=target_user.pk)


class AdminUserDeleteView(PermissionRequiredMixin, View):
    required_permission = 'admin.manage'

    def post(self, request, pk, *args, **kwargs):
        target_user = get_object_or_404(User, pk=pk)
        username = target_user.username
        target_user.delete()
        log_audit_action(request.user, 'DELETE_USER', target_type='User', target_id=pk, details={'username': username}, request=request)
        messages.success(request, f"User '{username}' deleted successfully.")
        return redirect('admin_panel:user_list')


class AdminVehicleCreateView(PermissionRequiredMixin, View):
    required_permission = 'vehicles.manage'

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        make_model = request.POST.get('make_model', '').strip()
        license_plate = request.POST.get('license_plate', '').strip()
        color = request.POST.get('color', '').strip()
        features = request.POST.get('features', '').strip()

        owner = get_object_or_404(User, pk=user_id)
        vehicle = Vehicle.objects.create(
            user=owner,
            make_model=make_model,
            license_plate=license_plate,
            color=color,
            features=features
        )
        log_audit_action(request.user, 'CREATE_VEHICLE', target_type='Vehicle', target_id=vehicle.id, request=request)
        messages.success(request, f"Vehicle '{vehicle.make_model}' added for {owner.username}.")
        return redirect('admin_panel:vehicle_list')


class AdminVehicleEditView(PermissionRequiredMixin, View):
    required_permission = 'vehicles.manage'

    def post(self, request, pk, *args, **kwargs):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        vehicle.make_model = request.POST.get('make_model', '').strip()
        vehicle.license_plate = request.POST.get('license_plate', '').strip()
        vehicle.color = request.POST.get('color', '').strip()
        vehicle.features = request.POST.get('features', '').strip()
        vehicle.save()

        log_audit_action(request.user, 'UPDATE_VEHICLE', target_type='Vehicle', target_id=vehicle.id, request=request)
        messages.success(request, f"Vehicle #{vehicle.id} updated successfully.")
        return redirect('admin_panel:vehicle_list')


class AdminVehicleDeleteView(PermissionRequiredMixin, View):
    required_permission = 'vehicles.manage'

    def post(self, request, pk, *args, **kwargs):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        vehicle.delete()
        log_audit_action(request.user, 'DELETE_VEHICLE', target_type='Vehicle', target_id=pk, request=request)
        messages.success(request, f"Vehicle #{pk} deleted.")
        return redirect('admin_panel:vehicle_list')


class AdminRideCreateView(PermissionRequiredMixin, View):
    required_permission = 'rides.manage'

    def post(self, request, *args, **kwargs):
        driver_id = request.POST.get('driver_id')
        origin = request.POST.get('origin', '').strip()
        destination = request.POST.get('destination', '').strip()
        pickup_point = request.POST.get('pickup_point', '').strip()
        departure_time = request.POST.get('departure_time')
        price_per_seat = request.POST.get('price_per_seat', 0)
        available_seats = request.POST.get('available_seats', 1)
        status = request.POST.get('status', 'active')
        vehicle_info = request.POST.get('vehicle_info', '').strip()
        notes = request.POST.get('notes', '').strip()

        driver = get_object_or_404(User, pk=driver_id)
        ride = Ride.objects.create(
            driver=driver,
            origin=origin,
            destination=destination,
            pickup_point=pickup_point,
            departure_datetime=departure_time or timezone.now(),
            price_per_seat=price_per_seat,
            available_seats=available_seats,
            status=status,
            vehicle_info=vehicle_info,
            notes=notes
        )
        log_audit_action(request.user, 'CREATE_RIDE', target_type='Ride', target_id=ride.id, request=request)
        messages.success(request, f"Ride #{ride.id} created successfully.")
        return redirect('admin_panel:ride_list')


class AdminRideEditView(PermissionRequiredMixin, View):
    required_permission = 'rides.manage'

    def post(self, request, pk, *args, **kwargs):
        ride = get_object_or_404(Ride, pk=pk)
        ride.origin = request.POST.get('origin', ride.origin).strip()
        ride.destination = request.POST.get('destination', ride.destination).strip()
        ride.pickup_point = request.POST.get('pickup_point', ride.pickup_point).strip()
        if request.POST.get('departure_time'):
            ride.departure_datetime = request.POST.get('departure_time')
        ride.price_per_seat = request.POST.get('price_per_seat', ride.price_per_seat)
        ride.available_seats = request.POST.get('available_seats', ride.available_seats)
        ride.status = request.POST.get('status', ride.status)
        ride.vehicle_info = request.POST.get('vehicle_info', ride.vehicle_info).strip()
        ride.notes = request.POST.get('notes', ride.notes).strip()
        ride.save()

        log_audit_action(request.user, 'UPDATE_RIDE', target_type='Ride', target_id=ride.id, request=request)
        messages.success(request, f"Ride #{ride.id} updated successfully.")
        return redirect('admin_panel:ride_detail', pk=ride.pk)


class AdminRideDeleteView(PermissionRequiredMixin, View):
    required_permission = 'rides.manage'

    def post(self, request, pk, *args, **kwargs):
        ride = get_object_or_404(Ride, pk=pk)
        ride.delete()
        log_audit_action(request.user, 'DELETE_RIDE', target_type='Ride', target_id=pk, request=request)
        messages.success(request, f"Ride #{pk} deleted.")
        return redirect('admin_panel:ride_list')


class AdminBookingCreateView(PermissionRequiredMixin, View):
    required_permission = 'bookings.manage'

    def post(self, request, *args, **kwargs):
        passenger_id = request.POST.get('passenger_id')
        ride_id = request.POST.get('ride_id')
        seats_booked = int(request.POST.get('seats_booked', 1))
        status = request.POST.get('status', 'confirmed')

        passenger = get_object_or_404(User, pk=passenger_id)
        ride = get_object_or_404(Ride, pk=ride_id)

        total_price = float(ride.price_per_seat) * seats_booked

        booking = Booking.objects.create(
            passenger=passenger,
            ride=ride,
            seats_booked=seats_booked,
            total_price=total_price,
            status=status
        )

        if status in ['pending', 'confirmed'] and ride.available_seats >= seats_booked:
            ride.available_seats -= seats_booked
            ride.save()

        log_audit_action(request.user, 'CREATE_BOOKING', target_type='Booking', target_id=booking.id, request=request)
        messages.success(request, f"Booking #{booking.id} created for {passenger.username}.")
        return redirect('admin_panel:booking_list')


class AdminBookingEditView(PermissionRequiredMixin, View):
    required_permission = 'bookings.manage'

    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)
        new_status = request.POST.get('status', booking.status)
        new_seats = int(request.POST.get('seats_booked', booking.seats_booked))

        booking.status = new_status
        booking.seats_booked = new_seats
        booking.total_price = float(booking.ride.price_per_seat) * new_seats
        booking.save()

        log_audit_action(request.user, 'UPDATE_BOOKING', target_type='Booking', target_id=booking.id, request=request)
        messages.success(request, f"Booking #{booking.id} updated.")
        return redirect('admin_panel:booking_list')


class AdminBookingDeleteView(PermissionRequiredMixin, View):
    required_permission = 'bookings.manage'

    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)
        booking.delete()
        log_audit_action(request.user, 'DELETE_BOOKING', target_type='Booking', target_id=pk, request=request)
        messages.success(request, f"Booking #{pk} deleted.")
        return redirect('admin_panel:booking_list')


class AdminPaymentCreateView(PermissionRequiredMixin, View):
    required_permission = 'payments.refund'

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        booking_id = request.POST.get('booking_id')
        amount = request.POST.get('amount', 0)
        status = request.POST.get('status', 'completed')
        transaction_id = request.POST.get('transaction_id', '').strip()
        payment_method = request.POST.get('payment_method', 'card')

        user = get_object_or_404(User, pk=user_id)
        booking = Booking.objects.filter(id=booking_id).first() if booking_id else None

        payment = Payment.objects.create(
            user=user,
            booking=booking,
            amount=amount,
            status=status,
            transaction_id=transaction_id or None,
            payment_method=payment_method
        )
        log_audit_action(request.user, 'CREATE_PAYMENT', target_type='Payment', target_id=payment.id, request=request)
        messages.success(request, f"Payment #{payment.id} logged.")
        return redirect('admin_panel:payment_list')


class AdminPaymentEditView(PermissionRequiredMixin, View):
    required_permission = 'payments.refund'

    def post(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(Payment, pk=pk)
        payment.status = request.POST.get('status', payment.status)
        payment.amount = request.POST.get('amount', payment.amount)
        payment.payment_method = request.POST.get('payment_method', payment.payment_method)
        payment.save()

        log_audit_action(request.user, 'UPDATE_PAYMENT', target_type='Payment', target_id=payment.id, request=request)
        messages.success(request, f"Payment #{payment.id} status updated to {payment.status}.")
        return redirect('admin_panel:payment_list')


class AdminPaymentDeleteView(PermissionRequiredMixin, View):
    required_permission = 'payments.refund'

    def post(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(Payment, pk=pk)
        payment.delete()
        log_audit_action(request.user, 'DELETE_PAYMENT', target_type='Payment', target_id=pk, request=request)
        messages.success(request, f"Payment #{pk} deleted.")
        return redirect('admin_panel:payment_list')


class AdminComplaintCreateView(PermissionRequiredMixin, View):
    required_permission = 'complaints.manage'

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'other')
        priority = request.POST.get('priority', 'medium')
        status = request.POST.get('status', 'OPEN')

        user = get_object_or_404(User, pk=user_id)
        complaint = Complaint.objects.create(
            user=user,
            subject=subject,
            description=description,
            category=category,
            priority=priority,
            status=status
        )
        log_audit_action(request.user, 'CREATE_COMPLAINT', target_type='Complaint', target_id=complaint.id, request=request)
        messages.success(request, f"Complaint ticket #{complaint.id} created.")
        return redirect('admin_panel:complaint_list')


class AdminComplaintDeleteView(PermissionRequiredMixin, View):
    required_permission = 'complaints.manage'

    def post(self, request, pk, *args, **kwargs):
        complaint = get_object_or_404(Complaint, pk=pk)
        complaint.delete()
        log_audit_action(request.user, 'DELETE_COMPLAINT', target_type='Complaint', target_id=pk, request=request)
        messages.success(request, f"Complaint #{pk} deleted.")
        return redirect('admin_panel:complaint_list')


class AdminVerificationCreateView(PermissionRequiredMixin, View):
    required_permission = 'verification.review'

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        verification_type = request.POST.get('verification_type', 'veriff')
        session_id = request.POST.get('session_id', '').strip()
        status = request.POST.get('status', 'APPROVED')
        reason = request.POST.get('reason', '').strip()

        user = get_object_or_404(User, pk=user_id)
        ver = VerificationRecord.objects.create(
            user=user,
            verification_type=verification_type,
            session_id=session_id,
            status=status,
            decision_reason=reason
        )
        if status == 'APPROVED':
            user.is_verified_driver = True
            user.save()

        log_audit_action(request.user, 'CREATE_VERIFICATION', target_type='VerificationRecord', target_id=ver.id, request=request)
        messages.success(request, f"Verification record #{ver.id} logged.")
        return redirect('admin_panel:verification_list')


class AdminVerificationDeleteView(PermissionRequiredMixin, View):
    required_permission = 'verification.review'

    def post(self, request, pk, *args, **kwargs):
        ver = get_object_or_404(VerificationRecord, pk=pk)
        ver.delete()
        log_audit_action(request.user, 'DELETE_VERIFICATION', target_type='VerificationRecord', target_id=pk, request=request)
        messages.success(request, f"Verification record #{pk} deleted.")
        return redirect('admin_panel:verification_list')

