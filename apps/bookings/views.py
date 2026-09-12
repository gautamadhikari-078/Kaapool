from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy

from rest_framework import viewsets, permissions
from .models import Booking
from apps.rides.models import Ride
from .serializers import BookingSerializer


# --- Web Views ---

class MyBookingsView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'bookings/my_bookings.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return Booking.objects.filter(passenger=self.request.user).select_related('ride', 'ride__driver')


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = Booking
    template_name = 'bookings/detail.html'
    context_object_name = 'booking'


class BookingCheckoutView(LoginRequiredMixin, View):
    """Renders the checkout page ('Book online and secure your seat') matching Image 1."""
    def get(self, request, ride_id, *args, **kwargs):
        ride = get_object_or_404(Ride, pk=ride_id, status='active')

        if ride.driver == request.user:
            messages.error(request, "You cannot book your own offered ride.")
            return redirect('rides:detail', pk=ride.pk)

        try:
            seats_booked = int(request.GET.get('seats', 1))
        except (ValueError, TypeError):
            seats_booked = 1

        seats_booked = min(max(1, seats_booked), max(1, ride.available_seats))
        total_price = ride.price_per_seat * seats_booked

        default_message = f"Hello, I've just booked your ride! I'd be glad to travel with you. Can I get more information on...?"

        context = {
            'ride': ride,
            'seats_booked': seats_booked,
            'total_price': total_price,
            'default_message': default_message,
        }
        return render(request, 'bookings/checkout.html', context)


class BookingCreateView(LoginRequiredMixin, View):
    """Handles finalize reservation when user clicks 'Book' on checkout screen."""
    def post(self, request, *args, **kwargs):
        ride_id = request.POST.get('ride_id')
        try:
            seats_booked = int(request.POST.get('seats_booked', 1))
        except (ValueError, TypeError):
            seats_booked = 1

        ride = get_object_or_404(Ride, pk=ride_id, status='active')

        if ride.driver == request.user:
            messages.error(request, "You cannot book your own offered ride.")
            return redirect('rides:detail', pk=ride.pk)

        if seats_booked > ride.available_seats or ride.available_seats <= 0:
            messages.error(request, f"Sorry, only {ride.available_seats} seat(s) are available.")
            return redirect('rides:detail', pk=ride.pk)

        total_price = ride.price_per_seat * seats_booked

        booking = Booking.objects.create(
            passenger=request.user,
            ride=ride,
            seats_booked=seats_booked,
            total_price=total_price,
            status='confirmed'
        )

        ride.available_seats -= seats_booked
        ride.save()

        return redirect('bookings:success', pk=booking.pk)


class BookingSuccessView(LoginRequiredMixin, DetailView):
    """Renders the success confirmation screen ('Booked! Enjoy your ride') with 3s auto redirect matching Image 2."""
    model = Booking
    template_name = 'bookings/success.html'
    context_object_name = 'booking'


class BookingCancelReasonView(LoginRequiredMixin, View):
    """Renders the reason selection screen ('What's the reason?') matching Image 2."""
    def get(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, passenger=request.user)
        
        reasons = [
            "The car owner changed the date/schedule",
            "I found another ride",
            "The car owner asked me to cancel",
            "The date is no longer suitable",
            "I made a mistake and shouldn't have booked",
            "I found another means of transportation",
            "The car owner is no longer offering the ride",
            "The car owner is unreachable",
            "The driver changed the pick-up point",
            "Something came up, I'm no longer travelling at all"
        ]
        
        return render(request, 'bookings/cancel_reason.html', {'booking': booking, 'reasons': reasons})


class BookingCancelCommentView(LoginRequiredMixin, View):
    """Renders the comment input screen ('Could you tell us a bit more?') matching Image 3."""
    def get(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, passenger=request.user)
        selected_reason = request.GET.get('reason', '')
        
        return render(request, 'bookings/cancel_comment.html', {'booking': booking, 'selected_reason': selected_reason})


class BookingCancelConfirmView(LoginRequiredMixin, View):
    """Executes cancellation, restores ride available seats, and redirects back to Ride plan."""
    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, passenger=request.user)
        
        if booking.status != 'cancelled':
            booking.status = 'cancelled'
            booking.cancellation_reason = request.POST.get('reason', '')
            booking.cancellation_comment = request.POST.get('comment', '')
            booking.save()
            
            # Restore available seats back on the ride
            booking.ride.available_seats += booking.seats_booked
            booking.ride.save()
            
            messages.success(request, "Your booking has been cancelled.")
            
        return redirect('bookings:detail', pk=booking.pk)


# --- REST API ViewSets ---

class APIBookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(passenger=user) | Booking.objects.filter(ride__driver=user)

    def perform_create(self, serializer):
        serializer.save(passenger=self.request.user)
