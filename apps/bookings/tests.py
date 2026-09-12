from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from apps.rides.models import Ride
from .models import Booking

User = get_user_model()


class BookingWebFlowTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(username='driver2', password='password123')
        self.passenger = User.objects.create_user(username='passenger1', password='password123')
        self.ride = Ride.objects.create(
            driver=self.driver,
            origin='Gurugram',
            destination='Rohtak',
            departure_time=timezone.now(),
            available_seats=4,
            price_per_seat=150.00
        )

    def test_checkout_view_authenticated(self):
        self.client.login(username='passenger1', password='password123')
        response = self.client.get(reverse('bookings:checkout', kwargs={'ride_id': self.ride.id}) + '?seats=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book online and secure your seat')
        self.assertContains(response, 'Gurugram')
        self.assertContains(response, 'Rohtak')

    def test_booking_create_redirects_to_success(self):
        self.client.login(username='passenger1', password='password123')
        response = self.client.post(reverse('bookings:create'), {
            'ride_id': self.ride.id,
            'seats_booked': 1
        })
        booking = Booking.objects.get(passenger=self.passenger, ride=self.ride)
        self.assertRedirects(response, reverse('bookings:success', kwargs={'pk': booking.id}))

    def test_success_view(self):
        booking = Booking.objects.create(
            passenger=self.passenger,
            ride=self.ride,
            seats_booked=1,
            total_price=150.00,
            status='confirmed'
        )
        self.client.login(username='passenger1', password='password123')
        response = self.client.get(reverse('bookings:success', kwargs={'pk': booking.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Booked! Enjoy your ride')
        self.assertContains(response, 'Redirecting to Your Rides in')

    def test_my_bookings_view(self):
        Booking.objects.create(
            passenger=self.passenger,
            ride=self.ride,
            seats_booked=1,
            total_price=150.00,
            status='confirmed'
        )
        self.client.login(username='passenger1', password='password123')
        response = self.client.get(reverse('bookings:my_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your rides')
        self.assertContains(response, 'Gurugram')

    def test_cancel_booking_flow(self):
        booking = Booking.objects.create(
            passenger=self.passenger,
            ride=self.ride,
            seats_booked=1,
            total_price=150.00,
            status='confirmed'
        )
        self.ride.available_seats = 3
        self.ride.save()

        self.client.login(username='passenger1', password='password123')

        # 1. Reason selection screen
        response_reason = self.client.get(reverse('bookings:cancel_reason', kwargs={'pk': booking.id}))
        self.assertEqual(response_reason.status_code, 200)
        self.assertContains(response_reason, "What's the reason?")

        # 2. Comment screen
        response_comment = self.client.get(reverse('bookings:cancel_comment', kwargs={'pk': booking.id}) + '?reason=I+found+another+ride')
        self.assertEqual(response_comment.status_code, 200)
        self.assertContains(response_comment, "Could you tell us a bit more?")

        # 3. Submit cancellation POST
        response_confirm = self.client.post(reverse('bookings:cancel_confirm', kwargs={'pk': booking.id}), {
            'reason': 'I found another ride',
            'comment': 'Plans changed'
        })
        self.assertRedirects(response_confirm, reverse('bookings:detail', kwargs={'pk': booking.id}))

        # Refresh from DB
        booking.refresh_from_db()
        self.ride.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertEqual(booking.cancellation_reason, 'I found another ride')
        self.assertEqual(self.ride.available_seats, 4) # seat restored

        # Check details page shows Cancelled banner
        response_detail = self.client.get(reverse('bookings:detail', kwargs={'pk': booking.id}))
        self.assertEqual(response_detail.status_code, 200)
        self.assertContains(response_detail, 'Cancelled')
