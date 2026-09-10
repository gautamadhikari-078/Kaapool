from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username='testdriver',
            email='driver@example.com',
            password='password123',
            phone_number='+1234567890'
        )
        self.assertEqual(user.username, 'testdriver')
        self.assertEqual(user.phone_number, '+1234567890')
        self.assertFalse(user.is_verified_driver)
