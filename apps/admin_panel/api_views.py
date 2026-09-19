import json
from rest_framework import views, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.rides.models import Ride, Vehicle
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.notifications.models import Notification
from apps.admin_panel.models import (
    VerificationRecord, Complaint, FAQ, Blog, WebsiteContent, AuditLog
)

User = get_user_model()


class IsAdminUserPermission(permissions.BasePermission):
    """DRF permission check to ensure caller is an authenticated admin."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            not getattr(request.user, 'is_blocked', False) and
            getattr(request.user, 'is_admin', False)
        )


class APIAdminUserListView(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        query = request.GET.get('q', '')
        users = User.objects.all().order_by('-date_joined')
        if query:
            users = users.filter(
                Q(first_name__icontains=query) | Q(username__icontains=query) | Q(email__icontains=query)
            )
        data = [{
            'id': u.id,
            'name': u.get_full_name() or u.username,
            'email': u.email,
            'phone': u.phone_number,
            'role': u.role,
            'is_verified': u.is_verified_driver,
            'is_blocked': u.is_blocked,
            'date_joined': u.date_joined.strftime('%Y-%m-%d %H:%M')
        } for u in users[:50]]
        return Response({'results': data, 'count': len(data)})


class APIAdminVerificationListView(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        verifications = VerificationRecord.objects.select_related('user').order_by('-updated_at')[:50]
        data = [{
            'id': v.id,
            'user': v.user.get_full_name() or v.user.username,
            'verification_type': v.verification_type,
            'session_id': v.session_id,
            'status': v.status,
            'reason': v.decision_reason,
            'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M')
        } for v in verifications]
        return Response({'results': data})


class APIAdminRideListView(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        rides = Ride.objects.select_related('driver').order_by('-created_at')[:50]
        data = [{
            'id': r.id,
            'driver': r.driver.get_full_name() or r.driver.username,
            'origin': r.origin,
            'destination': r.destination,
            'departure_time': r.departure_time.strftime('%Y-%m-%d %H:%M'),
            'price': float(r.price_per_seat),
            'seats': r.available_seats,
            'status': r.status
        } for r in rides]
        return Response({'results': data})


class APIAdminBookingListView(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        bookings = Booking.objects.select_related('passenger', 'ride').order_by('-created_at')[:50]
        data = [{
            'id': b.id,
            'passenger': b.passenger.get_full_name() or b.passenger.username,
            'ride_id': b.ride.id,
            'seats_booked': b.seats_booked,
            'total_price': float(b.total_price),
            'status': b.status,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M')
        } for b in bookings]
        return Response({'results': data})


class APIAdminFAQViewSet(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        faqs = FAQ.objects.all().order_by('display_order', '-created_at')
        data = [{
            'id': f.id,
            'question': f.question,
            'answer': f.answer,
            'category': f.category,
            'is_published': f.is_published,
            'display_order': f.display_order
        } for f in faqs]
        return Response({'results': data})

    def post(self, request):
        question = request.data.get('question')
        answer = request.data.get('answer')
        category = request.data.get('category', 'general')
        if not question or not answer:
            return Response({'error': 'Question and answer are required.'}, status=400)
        faq = FAQ.objects.create(question=question, answer=answer, category=category)
        return Response({'id': faq.id, 'status': 'created'}, status=201)


class APIAdminBlogViewSet(views.APIView):
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        blogs = Blog.objects.all().order_by('-created_at')
        data = [{
            'id': b.id,
            'title': b.title,
            'slug': b.slug,
            'category': b.category,
            'author': b.author_name,
            'is_published': b.is_published,
            'published_at': b.published_at.strftime('%Y-%m-%d') if b.published_at else None
        } for b in blogs]
        return Response({'results': data})
