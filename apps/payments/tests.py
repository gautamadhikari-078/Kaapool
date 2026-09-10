from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Payment

User = get_user_model()


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='payuser', password='password123')

    def test_create_payment(self):
        payment = Payment.objects.create(
            user=self.user,
            amount=25.50,
            status='completed',
            transaction_id='TXN123456'
        )
        self.assertEqual(payment.amount, 25.50)
        self.assertEqual(payment.status, 'completed')
