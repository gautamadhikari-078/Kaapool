from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from rest_framework import viewsets, permissions
from .models import Ride
from .serializers import RideSerializer


# --- Web Views ---

class RideSearchView(ListView):
    model = Ride
    template_name = 'rides/search.html'
    context_object_name = 'rides'

    def get_queryset(self):
        return Ride.objects.filter(status='active')


class RideCreateView(LoginRequiredMixin, CreateView):
    model = Ride
    template_name = 'rides/create.html'
    fields = ['origin', 'destination', 'pickup_point', 'departure_time', 'available_seats', 'price_per_seat', 'vehicle_info', 'notes']
    success_url = reverse_lazy('rides:my_rides')

    def form_valid(self, form):
        form.instance.driver = self.request.user
        return super().form_valid(form)


class RideDetailView(DetailView):
    model = Ride
    template_name = 'rides/detail.html'
    context_object_name = 'ride'


class MyRidesView(LoginRequiredMixin, ListView):
    model = Ride
    template_name = 'rides/my_rides.html'
    context_object_name = 'offered_rides'

    def get_queryset(self):
        return Ride.objects.filter(driver=self.request.user)


# --- REST API ViewSets ---

class APIRideViewSet(viewsets.ModelViewSet):
    queryset = Ride.objects.filter(status='active')
    serializer_class = RideSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)
