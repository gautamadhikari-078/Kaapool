from django.urls import path
from .views import (
    CustomLoginView, CustomLogoutView, SignUpView, EmailOTPVerifyView,
    NotificationPreferencesView, UnsubscribeView,
    DashboardView, ProfileView, PersonalDetailsView, EditPersonalDetailsView, RatingsView,
    AddVehicleView, VehicleDetailView, VehicleSpecsView, VehicleEditFeaturesView, VehicleDeleteView,
    ProfilePictureChoiceView, ProfilePictureEditView,
    DeleteProfilePictureView, VerifyIdView,
    DocumentSelectView, DocumentUploadView, DocumentViewView,
    SumsubVerifyAPIView, SumsubWebhookView,
    PasswordResetRequestView, PasswordResetConfirmView,
    TravelPreferencesView
)

app_name = 'accounts'

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('verify-email/', EmailOTPVerifyView.as_view(), name='verify_email'),
    path('notification-preferences/', NotificationPreferencesView.as_view(), name='notification_preferences'),
    path('unsubscribe/', UnsubscribeView.as_view(), name='unsubscribe'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/personal-details/', PersonalDetailsView.as_view(), name='personal_details'),
    path('profile/personal-details/edit/', EditPersonalDetailsView.as_view(), name='edit_personal_details'),
    path('profile/travel-preferences/', TravelPreferencesView.as_view(), name='travel_preferences'),
    path('profile/ratings/', RatingsView.as_view(), name='ratings'),
    path('profile/vehicle/add/', AddVehicleView.as_view(), name='add_vehicle'),
    path('profile/vehicle/<int:pk>/', VehicleDetailView.as_view(), name='vehicle_detail'),
    path('profile/vehicle/<int:pk>/specs/', VehicleSpecsView.as_view(), name='vehicle_specs'),
    path('profile/vehicle/<int:pk>/edit/', VehicleEditFeaturesView.as_view(), name='vehicle_edit'),
    path('profile/vehicle/<int:pk>/delete/', VehicleDeleteView.as_view(), name='vehicle_delete'),
    path('profile/picture/choice/', ProfilePictureChoiceView.as_view(), name='profile_picture_choice'),

    path('profile/picture/edit/', ProfilePictureEditView.as_view(), name='profile_picture_edit'),
    path('profile/picture/delete/', DeleteProfilePictureView.as_view(), name='delete_profile_picture'),
    path('profile/verify-id/', VerifyIdView.as_view(), name='verify_id'),
    path('profile/verify-id/document-select/', DocumentSelectView.as_view(), name='document_select'),
    path('profile/verify-id/upload/', DocumentUploadView.as_view(), name='document_upload'),
    path('profile/verify-id/document-view/', DocumentViewView.as_view(), name='document_view'),
    path('api/sumsub-verify/', SumsubVerifyAPIView.as_view(), name='sumsub_verify_api'),
    path('sumsub/webhook/', SumsubWebhookView.as_view(), name='sumsub_webhook'),
]
