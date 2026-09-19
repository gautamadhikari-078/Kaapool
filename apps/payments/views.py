from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework import viewsets, permissions
from .models import Payment
from .serializers import PaymentSerializer


# --- Web Views ---

class PaymentsHistoryView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'payments/payments.html'
    context_object_name = 'payments'

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related('booking', 'booking__ride').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_payments = Payment.objects.filter(user=self.request.user)
        
        from django.db.models import Sum
        total_spent = user_payments.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
        total_refunded = user_payments.filter(status='refunded').aggregate(total=Sum('amount'))['total'] or 0
        
        context['total_spent'] = total_spent
        context['total_refunded'] = total_refunded
        context['total_count'] = user_payments.count()
        context['completed_count'] = user_payments.filter(status='completed').count()
        return context


# --- REST API ViewSets ---

class APIPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
