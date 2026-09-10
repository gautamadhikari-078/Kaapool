from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class MessageModelTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')

    def test_create_message(self):
        msg = Message.objects.create(
            sender=self.user1,
            recipient=self.user2,
            content='Hi, is seat available?'
        )
        self.assertEqual(msg.content, 'Hi, is seat available?')
        self.assertFalse(msg.is_read)
