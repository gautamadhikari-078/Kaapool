"""
URL Configuration for Kaapool project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from apps.accounts.views import APIUserProfileView, APIRegisterView
from apps.rides.views import APIRideViewSet
from apps.bookings.views import APIBookingViewSet
from apps.payments.views import APIPaymentViewSet
from apps.notifications.views import APINotificationViewSet
from apps.messaging.views import APIMessageViewSet

# API v1 Router setup
router_v1 = DefaultRouter()
router_v1.register(r'rides', APIRideViewSet, basename='api-ride')
router_v1.register(r'bookings', APIBookingViewSet, basename='api-booking')
router_v1.register(r'payments', APIPaymentViewSet, basename='api-payment')
router_v1.register(r'notifications', APINotificationViewSet, basename='api-notification')
router_v1.register(r'messages', APIMessageViewSet, basename='api-message')

urlpatterns = [
    path('admin/', admin.site.urls),

    # Web Routes
    path('', include('apps.core.urls', namespace='core')),
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('rides/', include('apps.rides.urls', namespace='rides')),
    path('my-rides/', include(('apps.rides.urls', 'rides_my'), namespace='my_rides_direct')),
    path('bookings/', include('apps.bookings.urls', namespace='bookings')),
    path('my-bookings/', include(('apps.bookings.urls', 'bookings_my'), namespace='my_bookings_direct')),
    path('payments/', include('apps.payments.urls', namespace='payments')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('inbox/', include('apps.messaging.urls', namespace='messaging')),

    # API v1 Endpoints (For Future Web App & Mobile Application)
    path('api/v1/auth/register/', APIRegisterView.as_view(), name='api-register'),
    path('api/v1/users/me/', APIUserProfileView.as_view(), name='api-user-me'),
    path('api/v1/', include((router_v1.urls, 'api_v1'))),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
