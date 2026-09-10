from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='notifyuser', password='password123')

    def test_create_notification(self):
        notification = Notification.objects.create(
            user=self.user,
            title='Booking Update',
            message='Your ride booking has been confirmed.',
            notification_type='booking_confirmed'
        )
        self.assertEqual(notification.title, 'Booking Update')
        self.assertFalse(notification.is_read)
