import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError

from apps.rides.models import Ride, ReturnRideReminder
from apps.notifications.models import Notification
from apps.rides.services.return_ride_service import (
    validate_return_ride_timing,
    create_return_ride,
    schedule_return_ride_later,
    skip_return_ride,
    trigger_return_ride_reminder_if_needed,
    handle_ride_cancelled
)

User = get_user_model()


class RideModelTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user(username='driver1', password='password123')

    def test_create_ride(self):
        ride = Ride.objects.create(
            driver=self.driver,
            origin='Downtown',
            destination='Airport',
            departure_datetime=timezone.now() + datetime.timedelta(days=1),
            available_seats=3,
            price_per_seat=15.00
        )
        self.assertEqual(ride.available_seats, 3)
        self.assertIn(ride.status, ['scheduled', 'active'])
        self.assertFalse(ride.is_return_ride)
        self.assertIsNone(ride.original_ride)
        self.assertEqual(ride.return_ride_status, 'NOT_REQUESTED')


class ReturnRideEndToEndTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.driver = User.objects.create_user(
            username='driver_raj',
            email='raj@example.com',
            password='Password123!',
            is_verified_driver=True
        )
        self.admin = User.objects.create_superuser(
            username='super_admin',
            email='admin@kaapool.com',
            password='AdminPassword123!'
        )

        self.outbound_time = timezone.now() + datetime.timedelta(days=2)
        self.original_ride = Ride.objects.create(
            driver=self.driver,
            origin='Delhi',
            destination='Jaipur',
            pickup_address='Connaught Place, Delhi',
            drop_address='MI Road, Jaipur',
            pickup_latitude=28.6315,
            pickup_longitude=77.2167,
            drop_latitude=26.9124,
            drop_longitude=75.7873,
            departure_datetime=self.outbound_time,
            available_seats=4,
            price_per_seat=450.00,
            vehicle_info='Honda City (White) DL01AB1234',
            notes='Music and AC available'
        )

    # ----------------------------------------------------
    # TEST A: Skip Flow
    # ----------------------------------------------------
    def test_a_skip_flow(self):
        """
        Create Ride -> Return Ride Prompt -> Skip -> My Rides
        Verifies:
        - Status is marked SKIPPED
        - No return ride is created
        - User is safely redirected to My Rides
        """
        self.client.login(username='driver_raj', password='Password123!')

        # Access Return Ride Offer
        offer_url = reverse('rides:return_ride_offer', kwargs={'pk': self.original_ride.pk})
        response = self.client.get(offer_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Delhi')
        self.assertContains(response, 'Jaipur')

        # Click Skip
        skip_resp = self.client.post(offer_url, {'action': 'skip'})
        self.assertRedirects(skip_resp, reverse('rides:my_rides'))

        # Check DB State
        self.original_ride.refresh_from_db()
        self.assertEqual(self.original_ride.return_ride_status, 'SKIPPED')
        self.assertFalse(self.original_ride.has_return_ride)
        self.assertIsNone(self.original_ride.return_ride)

    # ----------------------------------------------------
    # TEST B: Make Return Ride (Immediate Creation) Flow
    # ----------------------------------------------------
    def test_b_create_immediately_flow(self):
        """
        Create Ride -> Make Return Ride -> Return Ride Form -> Validate & Create
        Verifies:
        - Reversal of Origin & Destination (Jaipur -> Delhi)
        - Validation: Return departure <= Original departure must be rejected
        - Return ride is created and foreign-key linked to original ride
        - Original ride return_ride_status updated to CREATED
        """
        self.client.login(username='driver_raj', password='Password123!')

        create_url = reverse('rides:return_ride_create', kwargs={'pk': self.original_ride.pk})

        # GET form: should prefill reversed locations
        get_resp = self.client.get(create_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Jaipur')
        self.assertContains(get_resp, 'Delhi')

        # Attempt invalid timing (departure earlier than original ride)
        earlier_date = (self.outbound_time - datetime.timedelta(hours=2)).strftime('%Y-%m-%d')
        earlier_time = (self.outbound_time - datetime.timedelta(hours=2)).strftime('%H:%M')
        invalid_post = self.client.post(create_url, {
            'origin': 'Jaipur',
            'destination': 'Delhi',
            'departure_date': earlier_date,
            'departure_time': earlier_time,
            'available_seats': 4,
            'price_per_seat': 450.00,
            'vehicle_info': 'Honda City'
        })
        self.assertEqual(invalid_post.status_code, 200)
        self.assertContains(invalid_post, 'cannot be scheduled before')
        self.assertFalse(self.original_ride.has_return_ride)

        # Submit valid return ride (8 hours after original departure)
        valid_date = (self.outbound_time + datetime.timedelta(hours=8)).strftime('%Y-%m-%d')
        valid_time = (self.outbound_time + datetime.timedelta(hours=8)).strftime('%H:%M')
        valid_post = self.client.post(create_url, {
            'origin': 'Jaipur',
            'destination': 'Delhi',
            'departure_date': valid_date,
            'departure_time': valid_time,
            'available_seats': 4,
            'price_per_seat': 450.00,
            'vehicle_info': 'Honda City'
        })
        self.assertRedirects(valid_post, reverse('rides:my_rides'))

        # Verify DB Relationships
        self.original_ride.refresh_from_db()
        self.assertEqual(self.original_ride.return_ride_status, 'CREATED')
        self.assertTrue(self.original_ride.has_return_ride)

        return_ride = self.original_ride.return_ride
        self.assertIsNotNone(return_ride)
        self.assertEqual(return_ride.original_ride, self.original_ride)
        self.assertTrue(return_ride.is_return_ride)
        self.assertEqual(return_ride.origin, 'Jaipur')
        self.assertEqual(return_ride.destination, 'Delhi')
        self.assertEqual(return_ride.driver, self.driver)

    # ----------------------------------------------------
    # TEST C: Schedule Later Flow & Notification on Completion
    # ----------------------------------------------------
    def test_c_schedule_later_and_completion_reminder(self):
        """
        Create Ride -> Schedule Later -> Ride Completes -> Notification Triggered -> User Opens
        Verifies:
        - Status set to SCHEDULED_FOR_LATER and ReturnRideReminder created with PENDING
        - Original ride remaining active does NOT trigger notification
        - Original ride completion triggers in-app notification with CTA link
        - Clicking prompt marks reminder as OPENED
        """
        self.client.login(username='driver_raj', password='Password123!')

        # Choose Schedule for Later
        offer_url = reverse('rides:return_ride_offer', kwargs={'pk': self.original_ride.pk})
        sched_resp = self.client.post(offer_url, {'action': 'schedule_later'})
        self.assertRedirects(sched_resp, reverse('rides:my_rides'))

        self.original_ride.refresh_from_db()
        self.assertEqual(self.original_ride.return_ride_status, 'SCHEDULED_FOR_LATER')

        reminder = ReturnRideReminder.objects.get(original_ride=self.original_ride)
        self.assertEqual(reminder.status, 'PENDING')
        self.assertIsNone(reminder.triggered_at)

        # Verify no notification yet while ride is scheduled
        notif_count = Notification.objects.filter(user=self.driver, notification_type='return_ride_reminder').count()
        self.assertEqual(notif_count, 0)

        # Complete the original ride
        complete_url = reverse('rides:complete', kwargs={'pk': self.original_ride.pk})
        comp_resp = self.client.post(complete_url)
        self.assertEqual(comp_resp.status_code, 302)

        self.original_ride.refresh_from_db()
        self.assertEqual(self.original_ride.status, 'completed')
        self.assertIsNotNone(self.original_ride.completed_at)

        # Verify Return Ride Reminder triggered
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, 'TRIGGERED')
        self.assertIsNotNone(reminder.triggered_at)

        # Verify in-app Notification generated
        notif = Notification.objects.filter(user=self.driver, notification_type='return_ride_reminder').first()
        self.assertIsNotNone(notif)
        self.assertIn('Delhi', notif.message)
        self.assertIn('Jaipur', notif.message)
        self.assertTrue(bool(notif.link))

        # User opens prompt from notification link
        open_resp = self.client.get(notif.link)
        self.assertEqual(open_resp.status_code, 200)

        reminder.refresh_from_db()
        self.assertEqual(reminder.status, 'OPENED')

    # ----------------------------------------------------
    # TEST D: Duplicate Prevention
    # ----------------------------------------------------
    def test_d_duplicate_prevention(self):
        """
        Verify that multiple return rides cannot be created for the same original ride.
        """
        self.client.login(username='driver_raj', password='Password123!')

        # Create first return ride
        valid_return_dt = self.outbound_time + datetime.timedelta(hours=6)
        create_return_ride(self.original_ride, self.driver, {
            'origin': 'Jaipur',
            'destination': 'Delhi',
            'departure_datetime': valid_return_dt,
            'available_seats': 3,
            'price_per_seat': 400.00
        })

        self.original_ride.refresh_from_db()
        self.assertTrue(self.original_ride.has_return_ride)

        # Attempt to create second return ride via service -> raises ValidationError
        with self.assertRaises(ValidationError):
            create_return_ride(self.original_ride, self.driver, {
                'origin': 'Jaipur',
                'destination': 'Delhi',
                'departure_datetime': valid_return_dt + datetime.timedelta(hours=2),
                'available_seats': 3,
                'price_per_seat': 400.00
            })

        # Attempt to access return ride creation view -> redirects with warning
        create_url = reverse('rides:return_ride_create', kwargs={'pk': self.original_ride.pk})
        resp = self.client.get(create_url)
        self.assertRedirects(resp, reverse('rides:detail', kwargs={'pk': self.original_ride.return_ride.id}))

    # ----------------------------------------------------
    # TEST E: Cancellation Flow
    # ----------------------------------------------------
    def test_e_cancellation_flow(self):
        """
        Cancel original ride -> verify return ride reminder is cancelled and notification is NOT triggered.
        """
        self.client.login(username='driver_raj', password='Password123!')

        # Schedule for later
        schedule_return_ride_later(self.original_ride, self.driver)
        reminder = ReturnRideReminder.objects.get(original_ride=self.original_ride)
        self.assertEqual(reminder.status, 'PENDING')

        # Cancel the ride
        cancel_url = reverse('rides:cancel', kwargs={'pk': self.original_ride.pk})
        self.client.post(cancel_url)

        self.original_ride.refresh_from_db()
        self.assertEqual(self.original_ride.status, 'cancelled')

        # Reminder must be cancelled
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, 'CANCELLED')

        # Triggering completion manually must not generate notifications for cancelled ride
        self.original_ride.status = 'cancelled'
        self.original_ride.save()
        trigger_return_ride_reminder_if_needed(self.original_ride)

        notif_count = Notification.objects.filter(user=self.driver, notification_type='return_ride_reminder').count()
        self.assertEqual(notif_count, 0)

    # ----------------------------------------------------
    # TEST F: Super Admin Integration
    # ----------------------------------------------------
    def test_f_admin_integration(self):
        """
        Verify Super Admin dashboard metrics, ride list indicators, and ride detail view.
        """
        # Create a return ride for the original ride
        valid_return_dt = self.outbound_time + datetime.timedelta(hours=6)
        ret_ride = create_return_ride(self.original_ride, self.driver, {
            'origin': 'Jaipur',
            'destination': 'Delhi',
            'departure_datetime': valid_return_dt,
            'available_seats': 4,
            'price_per_seat': 450.00
        })

        self.client.login(username='super_admin', password='AdminPassword123!')

        # 1. Super Admin Dashboard Overview
        dash_url = reverse('admin_panel:dashboard')
        dash_resp = self.client.get(dash_url)
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, 'Return Ride Overview')
        self.assertContains(dash_resp, 'Total Requests')
        self.assertEqual(dash_resp.context['return_rides_created'], 1)

        # 2. Super Admin Ride List
        list_url = reverse('admin_panel:ride_list')
        list_resp = self.client.get(list_url)
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'Return Ride')
        self.assertContains(list_resp, 'Created')

        # 3. Super Admin Ride Detail
        detail_url = reverse('admin_panel:ride_detail', kwargs={'pk': self.original_ride.pk})
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'Return Ride Relationship')
        self.assertContains(detail_resp, ret_ride.origin)
