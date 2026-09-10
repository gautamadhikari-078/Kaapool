from django.urls import path
from .views import MyBookingsView, BookingDetailView

app_name = 'bookings'

urlpatterns = [
    path('', MyBookingsView.as_view(), name='my_bookings'),
    path('my-bookings/', MyBookingsView.as_view(), name='list'),
    path('<int:pk>/', BookingDetailView.as_view(), name='detail'),
]
