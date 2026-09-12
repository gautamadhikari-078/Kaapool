from django.urls import path
from .views import (
    MyBookingsView,
    BookingDetailView,
    BookingCheckoutView,
    BookingCreateView,
    BookingSuccessView,
    BookingCancelReasonView,
    BookingCancelCommentView,
    BookingCancelConfirmView,
)

app_name = 'bookings'

urlpatterns = [
    path('', MyBookingsView.as_view(), name='my_bookings'),
    path('my-bookings/', MyBookingsView.as_view(), name='list'),
    path('checkout/<int:ride_id>/', BookingCheckoutView.as_view(), name='checkout'),
    path('create/', BookingCreateView.as_view(), name='create'),
    path('<int:pk>/success/', BookingSuccessView.as_view(), name='success'),
    path('<int:pk>/cancel/reason/', BookingCancelReasonView.as_view(), name='cancel_reason'),
    path('<int:pk>/cancel/comment/', BookingCancelCommentView.as_view(), name='cancel_comment'),
    path('<int:pk>/cancel/confirm/', BookingCancelConfirmView.as_view(), name='cancel_confirm'),
    path('<int:pk>/', BookingDetailView.as_view(), name='detail'),
]
