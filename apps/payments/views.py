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
        return Payment.objects.filter(user=self.request.user)


# --- REST API ViewSets ---

class APIPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
