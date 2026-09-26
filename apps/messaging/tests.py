import html
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from django.core.exceptions import ValidationError, PermissionDenied

from apps.rides.models import Ride
from apps.bookings.models import Booking
from apps.messaging.models import Conversation, ConversationParticipant, Message
from apps.messaging.services import (
    get_or_create_conversation_for_booking,
    send_message_service,
    mark_conversation_as_read
)

User = get_user_model()


class MessagingSystemTestCase(TestCase):
    def setUp(self):
        self.host_user = User.objects.create_user(
            username='host_user',
            email='host@example.com',
            password='Password123!',
            first_name='Host',
            last_name='User'
        )
        self.booker_user = User.objects.create_user(
            username='booker_user',
            email='booker@example.com',
            password='Password123!',
            first_name='Booker',
            last_name='User'
        )
        self.unauthorized_user = User.objects.create_user(
            username='stranger_user',
            email='stranger@example.com',
            password='Password123!',
            first_name='Stranger',
            last_name='User'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin_user',
            email='admin@example.com',
            password='Password123!',
            is_staff=True,
            is_superuser=True
        )

        # Create a Ride
        self.ride = Ride.objects.create(
            driver=self.host_user,
            origin='Jaipur',
            destination='Delhi',
            departure_datetime=timezone.now() + timedelta(days=2),
            available_seats=3,
            price_per_seat=450.00,
            status='scheduled'
        )

        # Create a confirmed Booking
        self.booking = Booking.objects.create(
            passenger=self.booker_user,
            ride=self.ride,
            seats_booked=1,
            total_price=450.00,
            status='confirmed'
        )

        # Initialize API client
        self.api_client = APIClient()

    def test_01_conversation_autoprovisioning_and_idempotency(self):
        """Test that conversation is automatically created for a confirmed booking and is idempotent."""
        conv1 = get_or_create_conversation_for_booking(self.booking)
        conv2 = get_or_create_conversation_for_booking(self.booking)

        self.assertEqual(conv1.id, conv2.id)
        self.assertEqual(conv1.ride, self.ride)
        self.assertEqual(conv1.booking, self.booking)
        self.assertEqual(Conversation.objects.count(), 1)

        participants = ConversationParticipant.objects.filter(conversation=conv1).values_list('user_id', flat=True)
        self.assertIn(self.host_user.id, participants)
        self.assertIn(self.booker_user.id, participants)

    def test_02_user_a_and_b_can_access_conversation(self):
        """User A (Host) and User B (Booker) can access the conversation API."""
        conv = get_or_create_conversation_for_booking(self.booking)

        # Host access
        self.api_client.force_authenticate(user=self.host_user)
        response_host = self.api_client.get(f'/inbox/api/conversations/{conv.id}/')
        self.assertEqual(response_host.status_code, status.HTTP_200_OK)

        # Booker access
        self.api_client.force_authenticate(user=self.booker_user)
        response_booker = self.api_client.get(f'/inbox/api/conversations/{conv.id}/')
        self.assertEqual(response_booker.status_code, status.HTTP_200_OK)

    def test_03_user_c_cannot_access_conversation_or_messages(self):
        """User C (Stranger) is denied access (403) to A/B conversation and messages."""
        conv = get_or_create_conversation_for_booking(self.booking)

        self.api_client.force_authenticate(user=self.unauthorized_user)

        # Attempt to access conversation detail
        response = self.api_client.get(f'/inbox/api/conversations/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt to access conversation messages
        response_msg = self.api_client.get(f'/inbox/api/conversations/{conv.id}/messages/')
        self.assertEqual(response_msg.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt to post message to conversation
        response_post = self.api_client.post(
            f'/inbox/api/conversations/{conv.id}/messages/',
            {'message': 'Hacking chat'},
            format='json'
        )
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)

    def test_04_message_sending_sanitization_and_unread_counts(self):
        """Test sending message, XSS sanitization, and unread count update."""
        conv = get_or_create_conversation_for_booking(self.booking)

        # Booker sends XSS payload
        raw_payload = "<script>alert('xss')</script> Pickup location kaha hai?"
        self.api_client.force_authenticate(user=self.booker_user)

        response = self.api_client.post(
            f'/inbox/api/conversations/{conv.id}/messages/',
            {'message': raw_payload},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        db_message = Message.objects.get(id=response.data['id'])
        self.assertNotIn('<script>', db_message.message_text)
        self.assertIn('&lt;script&gt;', db_message.message_text)

        # Check host unread count
        host_participant = ConversationParticipant.objects.get(conversation=conv, user=self.host_user)
        self.assertEqual(host_participant.unread_count, 1)

        # Host reads messages
        mark_conversation_as_read(conv, self.host_user)
        host_participant.refresh_from_db()
        self.assertEqual(host_participant.unread_count, 0)

    def test_05_oversized_message_rejection(self):
        """Test that oversized messages (>2000 chars) are rejected."""
        conv = get_or_create_conversation_for_booking(self.booking)
        self.api_client.force_authenticate(user=self.booker_user)

        large_payload = "A" * 2005
        response = self.api_client.post(
            f'/inbox/api/conversations/{conv.id}/messages/',
            {'message': large_payload},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_06_cancelled_booking_disables_chat(self):
        """Test that cancelled booking sets conversation to read_only and disables message sending."""
        conv = get_or_create_conversation_for_booking(self.booking)
        self.booking.status = 'cancelled'
        self.booking.save()

        conv.refresh_from_db()
        self.assertEqual(conv.status, 'read_only')

        self.api_client.force_authenticate(user=self.booker_user)
        response = self.api_client.post(
            f'/inbox/api/conversations/{conv.id}/messages/',
            {'message': 'Can I still get a ride?'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_07_offline_recipient_inbox_and_notifications(self):
        """Test that offline recipient gets message in inbox when opening later."""
        conv = get_or_create_conversation_for_booking(self.booking)

        send_message_service(conv, self.booker_user, "Offline check message")

        # Host opens inbox
        self.api_client.force_authenticate(user=self.host_user)
        response = self.api_client.get('/inbox/api/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['unread_count'], 1)

    def test_08_admin_conversation_view_permissions(self):
        """Test that staff admin can view conversation management endpoints while normal user cannot."""
        conv = get_or_create_conversation_for_booking(self.booking)

        client = Client()

        # Normal user cannot access admin conversations
        client.force_login(self.booker_user)
        response_user = client.get('/admin/conversations/')
        self.assertNotEqual(response_user.status_code, 200)

        # Admin user can access admin conversations
        client.force_login(self.admin_user)
        response_admin = client.get('/admin/conversations/')
        self.assertEqual(response_admin.status_code, 200)
        self.assertContains(response_admin, f"#{conv.id}")
