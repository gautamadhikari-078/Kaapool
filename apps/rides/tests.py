from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Ride

User = get_user_model()


class RideModelTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(username='driver1', password='password123')

    def test_create_ride(self):
        ride = Ride.objects.create(
            driver=self.driver,
            origin='Downtown',
            destination='Airport',
            departure_time=timezone.now(),
            available_seats=3,
            price_per_seat=15.00
        )
        self.assertEqual(ride.available_seats, 3)
        self.assertEqual(ride.status, 'active')
