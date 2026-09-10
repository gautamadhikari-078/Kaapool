from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework import viewsets, permissions
from .models import Booking
from .serializers import BookingSerializer


# --- Web Views ---

class MyBookingsView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'bookings/my_bookings.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return Booking.objects.filter(passenger=self.request.user)


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'bookings/detail.html'
    context_object_name = 'booking'


# --- REST API ViewSets ---

class APIBookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(passenger=user) | Booking.objects.filter(ride__driver=user)

    def perform_create(self, serializer):
        serializer.save(passenger=self.request.user)
