from django.urls import path
from apps.admin_panel.views import (
    AdminLoginView, AdminLogoutView, AdminPasswordResetRequestView, AdminPasswordResetConfirmView, AdminDashboardView,
    AdminUserListView, AdminUserDetailView, AdminUserActionView, AdminUserCreateView, AdminUserEditView, AdminUserDeleteView,
    AdminVerificationListView, AdminVerificationDetailView, AdminVerificationActionView, AdminVerificationCreateView, AdminVerificationDeleteView,
    AdminDriverListView,
    AdminVehicleListView, AdminVehicleCreateView, AdminVehicleEditView, AdminVehicleDeleteView,
    AdminRideListView, AdminRideDetailView, AdminRideCancelView, AdminRideCreateView, AdminRideEditView, AdminRideDeleteView,
    AdminBookingListView, AdminBookingDetailView, AdminBookingCreateView, AdminBookingEditView, AdminBookingDeleteView,
    AdminPaymentListView, AdminPaymentCreateView, AdminPaymentEditView, AdminPaymentDeleteView,
    AdminComplaintListView, AdminComplaintDetailView, AdminComplaintUpdateView, AdminComplaintCreateView, AdminComplaintDeleteView,
    AdminContactInquiryListView, AdminContactInquiryDetailView, AdminContactInquiryHistoryView, AdminContactInquiryReplyView, AdminContactInquiryDeleteView, AdminContactInquiryBulkDeleteView,
    AdminConversationListView, AdminConversationDetailView,
    AdminAdminsView, AdminSettingsView, AdminAuditLogView
)
from apps.admin_panel.api_views import (
    APIAdminUserListView, APIAdminVerificationListView,
    APIAdminRideListView, APIAdminBookingListView
)

app_name = 'admin_panel'

urlpatterns = [
    # Auth Routes
    path('login/', AdminLoginView.as_view(), name='login'),
    path('logout/', AdminLogoutView.as_view(), name='logout'),
    path('password-reset/', AdminPasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', AdminPasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Dashboard
    path('', AdminDashboardView.as_view(), name='dashboard'),
    path('dashboard/', AdminDashboardView.as_view(), name='dashboard_alt'),

    # User CRUD
    path('users/', AdminUserListView.as_view(), name='user_list'),
    path('users/create/', AdminUserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/', AdminUserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/edit/', AdminUserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', AdminUserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/action/', AdminUserActionView.as_view(), name='user_action'),

    # Verification CRUD
    path('verifications/', AdminVerificationListView.as_view(), name='verification_list'),
    path('verifications/create/', AdminVerificationCreateView.as_view(), name='verification_create'),
    path('verifications/<int:pk>/', AdminVerificationDetailView.as_view(), name='verification_detail'),
    path('verifications/<int:pk>/delete/', AdminVerificationDeleteView.as_view(), name='verification_delete'),
    path('verifications/<int:pk>/action/', AdminVerificationActionView.as_view(), name='verification_action'),

    # Driver & Vehicle CRUD
    path('drivers/', AdminDriverListView.as_view(), name='driver_list'),

    path('vehicles/', AdminVehicleListView.as_view(), name='vehicle_list'),
    path('vehicles/create/', AdminVehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicles/<int:pk>/edit/', AdminVehicleEditView.as_view(), name='vehicle_edit'),
    path('vehicles/<int:pk>/delete/', AdminVehicleDeleteView.as_view(), name='vehicle_delete'),

    # Ride CRUD
    path('rides/', AdminRideListView.as_view(), name='ride_list'),
    path('rides/create/', AdminRideCreateView.as_view(), name='ride_create'),
    path('rides/<int:pk>/', AdminRideDetailView.as_view(), name='ride_detail'),
    path('rides/<int:pk>/edit/', AdminRideEditView.as_view(), name='ride_edit'),
    path('rides/<int:pk>/delete/', AdminRideDeleteView.as_view(), name='ride_delete'),
    path('rides/<int:pk>/cancel/', AdminRideCancelView.as_view(), name='ride_cancel'),

    # Booking CRUD
    path('bookings/', AdminBookingListView.as_view(), name='booking_list'),
    path('bookings/create/', AdminBookingCreateView.as_view(), name='booking_create'),
    path('bookings/<int:pk>/', AdminBookingDetailView.as_view(), name='booking_detail'),
    path('bookings/<int:pk>/edit/', AdminBookingEditView.as_view(), name='booking_edit'),
    path('bookings/<int:pk>/delete/', AdminBookingDeleteView.as_view(), name='booking_delete'),

    # Payment CRUD
    path('payments/', AdminPaymentListView.as_view(), name='payment_list'),
    path('payments/create/', AdminPaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/edit/', AdminPaymentEditView.as_view(), name='payment_edit'),
    path('payments/<int:pk>/delete/', AdminPaymentDeleteView.as_view(), name='payment_delete'),

    # Complaint & Contact Inquiry CRUD
    path('complaints/', AdminComplaintListView.as_view(), name='complaint_list'),
    path('complaints/create/', AdminComplaintCreateView.as_view(), name='complaint_create'),
    path('complaints/<int:pk>/', AdminComplaintDetailView.as_view(), name='complaint_detail'),
    path('complaints/<int:pk>/delete/', AdminComplaintDeleteView.as_view(), name='complaint_delete'),
    path('complaints/<int:pk>/update/', AdminComplaintUpdateView.as_view(), name='complaint_update'),

    path('contact-inquiries/', AdminContactInquiryListView.as_view(), name='contact_inquiry_list'),
    path('contact-inquiries/bulk-delete/', AdminContactInquiryBulkDeleteView.as_view(), name='contact_inquiry_bulk_delete'),
    path('contact-inquiries/<int:pk>/', AdminContactInquiryDetailView.as_view(), name='contact_inquiry_detail'),
    path('contact-inquiries/<int:pk>/history/', AdminContactInquiryHistoryView.as_view(), name='contact_inquiry_history'),
    path('contact-inquiries/<int:pk>/reply/', AdminContactInquiryReplyView.as_view(), name='contact_inquiry_reply'),
    path('contact-inquiries/<int:pk>/delete/', AdminContactInquiryDeleteView.as_view(), name='contact_inquiry_delete'),

    # Admin Conversations
    path('conversations/', AdminConversationListView.as_view(), name='conversation_list'),
    path('conversations/<int:pk>/', AdminConversationDetailView.as_view(), name='conversation_detail'),

    # Admin Settings & Audit Logs
    path('admins/', AdminAdminsView.as_view(), name='admins_list'),
    path('settings/', AdminSettingsView.as_view(), name='settings'),
    path('audit-logs/', AdminAuditLogView.as_view(), name='audit_logs'),

    # REST APIs
    path('api/users/', APIAdminUserListView.as_view(), name='api_users'),
    path('api/verifications/', APIAdminVerificationListView.as_view(), name='api_verifications'),
    path('api/rides/', APIAdminRideListView.as_view(), name='api_rides'),
    path('api/bookings/', APIAdminBookingListView.as_view(), name='api_bookings'),
]
