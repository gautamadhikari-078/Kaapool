from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.rides.models import Ride
from .models import Booking

User = get_user_model()


class BookingModelTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(username='driver2', password='password123')
        self.passenger = User.objects.create_user(username='passenger1', password='password123')
        self.ride = Ride.objects.create(
            driver=self.driver,
            origin='City Center',
            destination='Suburbs',
            departure_time=timezone.now(),
            available_seats=4,
            price_per_seat=10.00
        )

    def test_create_booking(self):
        booking = Booking.objects.create(
            passenger=self.passenger,
            ride=self.ride,
            seats_booked=2,
            total_price=20.00
        )
        self.assertEqual(booking.seats_booked, 2)
        self.assertEqual(booking.status, 'pending')
