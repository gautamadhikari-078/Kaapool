from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib import messages
from django.views.generic import TemplateView, CreateView, UpdateView, View
from django.urls import reverse_lazy

from .forms import CustomUserCreationForm
from rest_framework import generics, permissions
from .serializers import UserSerializer, RegisterSerializer

User = get_user_model()


# --- Web Views ---

class CustomLoginView(DjangoLoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        ip_addr = self.request.META.get('REMOTE_ADDR', '')
        user_agent = self.request.META.get('HTTP_USER_AGENT', '')

        from django.utils import timezone
        now = timezone.now()

        # Security check for new device/IP
        if user.email and user.last_login_ip and (user.last_login_ip != ip_addr or (user.last_login_user_agent and user.last_login_user_agent != user_agent)):
            try:
                from apps.core.email_service import EmailService
                EmailService.send_new_device_login_alert(user, ip_addr, user_agent)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error sending login security email: {e}")

        user.last_login_at = now
        user.last_activity_at = now
        user.last_login_ip = ip_addr
        user.last_login_user_agent = user_agent
        user.save(update_fields=['last_login_at', 'last_activity_at', 'last_login_ip', 'last_login_user_agent'])

        user_display = user.get_full_name() or user.username
        messages.success(self.request, f" Welcome back, {user_display}! You have logged in successfully.")
        return response


class CustomLogoutView(DjangoLogoutView):
    next_page = 'core:home'

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, " You have logged out successfully. See you soon!")
        return super().dispatch(request, *args, **kwargs)


class SignUpView(CreateView):
    template_name = 'accounts/signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:verify_email')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.email_verified = False
        user.save()
        login(self.request, user)
        self.request.session['verify_user_id'] = user.id

        if user.email:
            try:
                from apps.core.email_service import EmailService
                EmailService.generate_and_send_otp(user, purpose='signup')
                messages.info(self.request, f" A 6-digit verification code has been sent to {user.email}.")
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error sending signup OTP: {e}")

        return redirect('accounts:verify_email')


import datetime

class EmailOTPVerifyView(LoginRequiredMixin, View):
    template_name = 'accounts/verify_email.html'

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.email_verified:
            messages.info(request, "Your email is already verified.")
            return redirect('accounts:personal_details')
        return render(request, self.template_name, {'user': user})

    def post(self, request, *args, **kwargs):
        user = request.user
        action = request.POST.get('action', 'verify')

        from apps.accounts.models import EmailOTP
        from django.utils import timezone
        from apps.core.email_service import EmailService

        if action == 'resend':
            fifteen_mins_ago = timezone.now() - datetime.timedelta(minutes=15)
            recent_resends = EmailOTP.objects.filter(user=user, purpose='signup', created_at__gte=fifteen_mins_ago).count()
            if recent_resends >= 3:
                messages.error(request, " Maximum resend attempts reached. Please wait 15 minutes before requesting another OTP.")
                return render(request, self.template_name, {'user': user, 'is_error': True})

            EmailService.generate_and_send_otp(user, purpose='signup')
            messages.success(request, f" A new 6-digit verification code has been sent to {user.email}.")
            return render(request, self.template_name, {'user': user, 'resent': True})

        otp_code = request.POST.get('otp_code', '').strip()
        if not otp_code or len(otp_code) != 6:
            messages.error(request, "Please enter the complete 6-digit verification code.")
            return render(request, self.template_name, {'user': user})

        otp_record = EmailOTP.objects.filter(user=user, purpose='signup', is_used=False).order_by('-created_at').first()
        if not otp_record:
            messages.error(request, "No active OTP found. Please click Resend OTP.")
            return render(request, self.template_name, {'user': user})

        if timezone.now() > otp_record.expires_at:
            messages.error(request, " Verification code has expired. Please click Resend OTP.")
            return render(request, self.template_name, {'user': user, 'expired': True})

        if otp_record.attempts_count >= 5:
            messages.error(request, " Too many incorrect attempts. Please click Resend OTP for a new code.")
            return render(request, self.template_name, {'user': user})

        if otp_record.otp_code != otp_code:
            otp_record.attempts_count += 1
            otp_record.save()
            messages.error(request, f" Incorrect verification code ({5 - otp_record.attempts_count} attempt(s) remaining).")
            return render(request, self.template_name, {'user': user})

        # Verification Success!
        otp_record.is_used = True
        otp_record.save()

        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save()

        try:
            EmailService.send_welcome_verified_email(user)
        except Exception:
            pass

        messages.success(request, " Email verified successfully! Welcome to Kaapool.")
        return redirect('accounts:personal_details')


class NotificationPreferencesView(LoginRequiredMixin, View):
    template_name = 'accounts/notification_preferences.html'

    def get(self, request, *args, **kwargs):
        from apps.notifications.models import NotificationPreference
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return render(request, self.template_name, {'pref': pref, 'user': request.user})

    def post(self, request, *args, **kwargs):
        from apps.notifications.models import NotificationPreference
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)

        pref.email_ride_updates = request.POST.get('email_ride_updates') == 'on'
        pref.email_messages = request.POST.get('email_messages') == 'on'
        pref.email_platform_updates = request.POST.get('email_platform_updates') == 'on'
        pref.email_marketing = request.POST.get('email_marketing') == 'on'
        pref.save()

        user = request.user
        user.marketing_consent = pref.email_marketing
        if not pref.email_marketing:
            from django.utils import timezone
            user.unsubscribed_at = timezone.now()
        else:
            user.unsubscribed_at = None
        user.save()

        messages.success(request, " Notification preferences updated successfully!")
        return render(request, self.template_name, {'pref': pref, 'user': user})


class UnsubscribeView(View):
    template_name = 'accounts/unsubscribe.html'

    def get(self, request, *args, **kwargs):
        email = request.GET.get('email', '').strip()
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                from django.utils import timezone
                user.marketing_consent = False
                user.unsubscribed_at = timezone.now()
                user.save()
                from apps.notifications.models import NotificationPreference
                pref, _ = NotificationPreference.objects.get_or_create(user=user)
                pref.email_marketing = False
                pref.save()

        return render(request, self.template_name, {'email': email})




class DashboardView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect('accounts:profile')



class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 4 Dynamic Steps for Profile Completion:
        # Step 1: Personal Information (Name or Bio)
        step1_done = bool((user.first_name and user.last_name) or user.bio)

        # Step 2: Email or Phone verified / provided
        step2_done = bool(user.is_phone_verified or user.email or user.phone_number)

        # Step 3: Profile picture uploaded
        step3_done = bool(user.profile_picture)

        # Step 4: Verify identity (driver/ID verification)
        step4_done = bool(user.is_verified_driver)

        completed_steps = sum([step1_done, step2_done, step3_done, step4_done])

        context['completed_steps'] = completed_steps
        context['total_steps'] = 4
        context['step1_done'] = step1_done
        context['step2_done'] = step2_done
        context['step3_done'] = step3_done
        context['step4_done'] = step4_done

        from apps.rides.models import Vehicle
        context['user_vehicles'] = Vehicle.objects.filter(user=user).order_by('-created_at')

        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        action = request.POST.get('action', '').strip()

        if action == 'add_vehicle':
            car_model = request.POST.get('car_model', '').strip()
            license_plate = request.POST.get('license_plate', '').strip().upper()
            color = request.POST.get('car_details', '').strip()
            if car_model:
                from apps.rides.models import Vehicle
                Vehicle.objects.create(
                    user=user,
                    make_model=car_model,
                    license_plate=license_plate,
                    color=color
                )
                messages.success(request, f" Vehicle '{car_model}' added to your profile!")
            return redirect('accounts:profile')

        if action == 'update_bio':
            bio = request.POST.get('bio', '').strip()
            user.bio = bio
            user.save(update_fields=['bio'])
            messages.success(request, " Mini bio updated successfully!")
            return redirect('accounts:profile')

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        bio = request.POST.get('bio', '').strip()

        if first_name: user.first_name = first_name
        if last_name: user.last_name = last_name
        if email: user.email = email
        if phone_number: user.phone_number = phone_number
        if bio: user.bio = bio

        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']

        user.save()
        messages.success(request, " Your profile details have been updated successfully!")
        return redirect('accounts:profile')


class VehicleDetailView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        from apps.rides.models import Vehicle
        vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)
        return render(request, 'accounts/vehicle_detail.html', {'vehicle': vehicle, 'user': request.user})


class VehicleEditFeaturesView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        from apps.rides.models import Vehicle
        vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)
        return render(request, 'accounts/vehicle_edit.html', {'vehicle': vehicle, 'user': request.user})

    def post(self, request, pk, *args, **kwargs):
        from apps.rides.models import Vehicle
        vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)
        
        make_model = request.POST.get('make_model', '').strip()
        color = request.POST.get('color', '').strip()
        license_plate = request.POST.get('license_plate', '').strip().upper()
        features_list = request.POST.getlist('features')
        is_electric = request.POST.get('is_electric', '')
        if is_electric:
            features_list.append('Fully electric')
        features = ", ".join(features_list)

        if make_model:
            vehicle.make_model = make_model
        if color:
            vehicle.color = color
        if license_plate:
            vehicle.license_plate = license_plate
        vehicle.features = features
        vehicle.save()

        messages.success(request, f" Vehicle '{vehicle.make_model}' updated successfully!")
        return redirect('accounts:vehicle_detail', pk=vehicle.pk)


class VehicleDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from apps.rides.models import Vehicle
        vehicle = get_object_or_404(Vehicle, pk=pk, user=request.user)
        make_name = vehicle.make_model
        vehicle.delete()
        messages.success(request, f" Vehicle '{make_name}' has been deleted.")
        return redirect('accounts:profile')





import base64
from django.core.files.base import ContentFile

class PersonalDetailsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'accounts/personal_details.html', {'user': request.user})


class EditPersonalDetailsView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        import datetime
        max_dob = (datetime.date.today() - datetime.timedelta(days=18*365.25)).strftime('%Y-%m-%d')
        return render(request, 'accounts/edit_personal_details.html', {'user': request.user, 'max_dob': max_dob})

    def post(self, request, *args, **kwargs):
        import datetime
        user = request.user
        first_name = request.POST.get('first_name', user.first_name).strip()
        last_name = request.POST.get('last_name', user.last_name).strip()
        dob_str = request.POST.get('date_of_birth', '').strip()
        email = request.POST.get('email', user.email).strip()
        phone_number = request.POST.get('phone_number', '').strip()
        bio = request.POST.get('bio', user.bio).strip()

        # Mobile Phone Compulsory Validation
        if not phone_number:
            messages.error(request, "⚠️ Mobile phone number is required.")
            max_dob = (datetime.date.today() - datetime.timedelta(days=18*365.25)).strftime('%Y-%m-%d')
            return render(request, 'accounts/edit_personal_details.html', {'user': user, 'max_dob': max_dob})

        # Date of Birth 18+ Validation
        dob_date = None
        if dob_str:
            try:
                dob_date = datetime.datetime.strptime(dob_str, '%Y-%m-%d').date()
                today = datetime.date.today()
                age = today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))
                if age < 18:
                    messages.error(request, " You must be at least 18 years old to use Kaapool.")
                    max_dob = (today - datetime.timedelta(days=18*365.25)).strftime('%Y-%m-%d')
                    return render(request, 'accounts/edit_personal_details.html', {'user': user, 'max_dob': max_dob})
            except ValueError:
                pass

        user.first_name = first_name
        user.last_name = last_name
        user.date_of_birth = dob_date
        user.email = email
        user.phone_number = phone_number
        user.bio = bio

        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']

        user.save()
        messages.success(request, " Personal details updated successfully!")
        return redirect('accounts:personal_details')


class DocumentViewView(LoginRequiredMixin, View):
    """Displays user's uploaded identity documents & verification status."""
    template_name = 'accounts/document_view.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'user': request.user})



class AddVehicleView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'accounts/add_vehicle.html', {'user': request.user})

    def post(self, request, *args, **kwargs):
        user = request.user
        make = request.POST.get('make', '').strip()
        model = request.POST.get('model', '').strip()
        license_plate = request.POST.get('license_plate', '').strip().upper()
        color = request.POST.get('color', '').strip()
        features_list = request.POST.getlist('features')
        is_electric = request.POST.get('is_electric', '')
        if is_electric:
            features_list.append('Fully electric')
        features = ", ".join(features_list)

        make_model = f"{make} {model}".strip() if model else make

        if make_model:
            from apps.rides.models import Vehicle
            Vehicle.objects.create(
                user=user,
                make_model=make_model,
                license_plate=license_plate,
                color=color,
                features=features
            )
            messages.success(request, f"🚗 Vehicle '{make_model}' added successfully!")

        return redirect('accounts:profile')


class RatingsView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        context = {
            'user': request.user,
            'average_rating': "1/5",
            'total_ratings': 1,
            'breakdown': [
                {'label': 'Excellent', 'count': 0},
                {'label': 'Good', 'count': 0},
                {'label': 'Okay', 'count': 0},
                {'label': 'Disappointing', 'count': 0},
                {'label': 'Very disappointing', 'count': 1},
            ],
            'reviews': [
                {
                    'reviewer_name': 'Kaapool',
                    'rating_label': 'Very disappointing',
                    'comment': 'Automatic rating: passenger cancelled late',
                    'date': 'Sept 2026',
                    'is_system': True,
                }
            ]
        }
        return render(request, 'accounts/ratings.html', context)


class ProfilePictureChoiceView(LoginRequiredMixin, TemplateView):

    template_name = 'accounts/picture_choice.html'


class ProfilePictureEditView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'accounts/picture_edit.html')

    def post(self, request, *args, **kwargs):
        user = request.user
        image_data = request.POST.get('cropped_image_data', '')
        
        if image_data and 'base64,' in image_data:
            format_str, imgstr = image_data.split(';base64,')
            ext = format_str.split('/')[-1]
            if ext == 'jpeg': ext = 'jpg'
            filename = f"user_{user.id}_avatar.{ext}"
            user.profile_picture.save(filename, ContentFile(base64.b64decode(imgstr)), save=True)
            messages.success(request, " Profile picture updated successfully!")
            return redirect('accounts:personal_details')
        elif 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            messages.success(request, " Profile picture updated successfully!")
            return redirect('accounts:personal_details')
        
        messages.warning(request, "Please choose an image first.")
        return redirect('accounts:personal_details')


class DeleteProfilePictureView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        user = request.user
        if user.profile_picture:
            user.profile_picture.delete(save=False)
            user.profile_picture = None
            user.save()
            messages.success(request, " Profile picture deleted successfully.")
        else:
            messages.info(request, "No profile picture to delete.")
        return redirect('accounts:profile')


from PIL import Image, ImageFilter, ImageOps
import numpy as np

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging
from .sumsub_service import sumsub_service

logger = logging.getLogger(__name__)

class VerifyIdView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/verify_id.html'


class DocumentSelectView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/document_select.html'


class DocumentUploadView(LoginRequiredMixin, View):
    template_name = 'accounts/document_upload.html'

    def get(self, request, *args, **kwargs):
        doc_type = request.GET.get('type', 'id_card')
        requires_back = doc_type in ['id_card', 'driver_license']
        return render(request, self.template_name, {
            'doc_type': doc_type,
            'requires_back': requires_back,
            'is_error': False,
            'is_verified': False,
            'is_review': False
        })

    def post(self, request, *args, **kwargs):
        doc_type = request.POST.get('doc_type', 'id_card')
        requires_back = doc_type in ['id_card', 'driver_license']
        
        front_file = request.FILES.get('id_document_front') or request.FILES.get('id_document')
        back_file = request.FILES.get('id_document_back') if requires_back else None

        doc_titles = {
            'id_card': 'Aadhaar Card',
            'driver_license': "Driver's License",
            'passport': 'Passport'
        }
        doc_title = doc_titles.get(doc_type, 'ID Card')
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')

        # Check presence
        if not front_file:
            err = f'Please select the front side photo of your {doc_title}.'
            if is_ajax:
                return JsonResponse({"status": "FAILED", "documentType": doc_type.upper(), "documentDetected": False, "authenticityCheck": "FAILED", "reason": err}, status=400)
            return render(request, self.template_name, {'doc_type': doc_type, 'requires_back': requires_back, 'is_error': True, 'error_message': err})

        if requires_back and not back_file:
            err = f'Please select both Front and Back side photos of your {doc_title}.'
            if is_ajax:
                return JsonResponse({"status": "FAILED", "documentType": doc_type.upper(), "documentDetected": False, "authenticityCheck": "FAILED", "reason": err}, status=400)
            return render(request, self.template_name, {'doc_type': doc_type, 'requires_back': requires_back, 'is_error': True, 'error_message': err})

        # Read file bytes securely
        front_bytes = front_file.read()
        front_filename = front_file.name
        back_bytes = back_file.read() if back_file else None
        back_filename = back_file.name if back_file else None

        # Execute Sumsub Verification Service
        result = sumsub_service.verify_identity_document(
            user=request.user,
            doc_type_input=doc_type,
            front_bytes=front_bytes,
            front_filename=front_filename,
            back_bytes=back_bytes,
            back_filename=back_filename
        )

        # Reset file pointers so full file contents are saved to media storage
        request.user.govt_id_type = doc_title
        if front_file:
            front_file.seek(0)
            request.user.govt_id_front = front_file
        if back_file:
            back_file.seek(0)
            request.user.govt_id_back = back_file

        ver_status = 'VERIFIED' if result.get('status') == 'VERIFIED' else 'PENDING'
        request.user.document_status = ver_status
        if ver_status == 'VERIFIED':
            request.user.is_verified_driver = True
        request.user.save()

        # Create/Update VerificationRecord in DB for Super Admin Panel
        from apps.admin_panel.models import VerificationRecord
        VerificationRecord.objects.create(
            user=request.user,
            verification_type='sumsub' if result.get('status') == 'VERIFIED' else 'manual',
            session_id=result.get('applicantId') or f"doc_{request.user.id}_{request.user.govt_id_type}",
            status='APPROVED' if result.get('status') == 'VERIFIED' else 'IN_PROGRESS',
            decision_reason=f"{doc_title} uploaded dynamically and saved to DB.",
            decision_payload=result
        )

        if result['status'] == 'VERIFIED':
            if is_ajax:
                return JsonResponse(result)

            messages.success(request, f"🎉 {doc_title} Uploaded & Verified Successfully!")
            return redirect('accounts:personal_details')

        elif result['status'] == 'REVIEW':
            if is_ajax:
                return JsonResponse(result)
            return render(request, self.template_name, {
                'doc_type': doc_type,
                'requires_back': requires_back,
                'is_review': True,
                'review_message': result['reason']
            })

        else: # FAILED
            if is_ajax:
                return JsonResponse(result, status=400)
            return render(request, self.template_name, {
                'doc_type': doc_type,
                'requires_back': requires_back,
                'is_error': True,
                'error_message': result['reason']
            })


class SumsubVerifyAPIView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        doc_type = request.POST.get('doc_type', 'id_card')
        requires_back = doc_type in ['id_card', 'driver_license']
        
        front_file = request.FILES.get('id_document_front') or request.FILES.get('id_document')
        back_file = request.FILES.get('id_document_back') if requires_back else None

        if not front_file:
            return JsonResponse({
                "status": "FAILED",
                "documentType": doc_type.upper(),
                "documentDetected": False,
                "authenticityCheck": "FAILED",
                "reason": "Please select the front photo of your document."
            }, status=400)

        if requires_back and not back_file:
            return JsonResponse({
                "status": "FAILED",
                "documentType": doc_type.upper(),
                "documentDetected": False,
                "authenticityCheck": "FAILED",
                "reason": "Please select both Front and Back side photos of your document."
            }, status=400)

        front_bytes = front_file.read()
        back_bytes = back_file.read() if back_file else None

        result = sumsub_service.verify_identity_document(
            user=request.user,
            doc_type_input=doc_type,
            front_bytes=front_bytes,
            front_filename=front_file.name,
            back_bytes=back_bytes,
            back_filename=back_file.name if back_file else None
        )

        if result['status'] == 'VERIFIED':
            request.user.is_verified_driver = True
            request.user.save()

        return JsonResponse(result, status=200 if result['status'] in ['VERIFIED', 'REVIEW'] else 400)


@method_decorator(csrf_exempt, name='dispatch')
class SumsubWebhookView(View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8'))
            applicant_id = payload.get('applicantId')
            external_user_id = payload.get('externalUserId')
            review_result = payload.get('reviewResult', {})
            review_answer = review_result.get('reviewAnswer')

            if external_user_id and review_answer == 'GREEN':
                user_id_str = str(external_user_id).replace('user_', '')
                User = get_user_model()
                user = User.objects.filter(id=user_id_str).first()
                if user:
                    user.is_verified_driver = True
                    user.save()
                    logger.info(f"User {user.id} verified via Sumsub webhook callback")

            return JsonResponse({"status": "ok"})
        except Exception as e:
            logger.error(f"Error handling Sumsub webhook: {e}")
            return JsonResponse({"error": str(e)}, status=400)




# --- Password Reset Views ---
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse


class PasswordResetRequestView(View):
    """Renders password reset request page and emails token link to user."""
    template_name = 'accounts/password_reset.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, "Please enter a valid email address.")
            return render(request, self.template_name)

        user = User.objects.filter(email__iexact=email).first()
        if user and user.is_active:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(
                reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
            )
            try:
                from apps.core.email_service import EmailService
                EmailService.send_password_reset_email(user, reset_url)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error sending password reset email: {e}")

        return render(request, 'accounts/password_reset_done.html', {'email': email})


class PasswordResetConfirmView(View):
    """Renders new password entry form after validating token link."""
    template_name = 'accounts/password_reset_confirm.html'

    def get_user_and_valid_token(self, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.filter(pk=uid).first()
            if user and default_token_generator.check_token(user, token):
                return user, True
        except (TypeError, ValueError, OverflowError):
            pass
        return None, False

    def get(self, request, uidb64, token, *args, **kwargs):
        user, is_valid = self.get_user_and_valid_token(uidb64, token)
        if not is_valid:
            return render(request, 'accounts/password_reset_invalid.html')
        return render(request, self.template_name, {'uidb64': uidb64, 'token': token})

    def post(self, request, uidb64, token, *args, **kwargs):
        user, is_valid = self.get_user_and_valid_token(uidb64, token)
        if not is_valid:
            return render(request, 'accounts/password_reset_invalid.html')

        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, self.template_name, {'uidb64': uidb64, 'token': token})

        if password != confirm_password:
            messages.error(request, "Passwords do not match. Please try again.")
            return render(request, self.template_name, {'uidb64': uidb64, 'token': token})

        user.set_password(password)
        user.save()

        # Log user in automatically after resetting password
        login(request, user)

        user_display = user.get_full_name() or user.username
        messages.success(request, f" Welcome back, {user_display}! Your password has been updated successfully and you are now logged in.")
        return redirect('accounts:profile')



# --- REST API Views ---


class APIUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class APIRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

