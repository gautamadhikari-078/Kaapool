from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Min, Q
from django.utils import timezone
import datetime

from rest_framework import viewsets, permissions
from .models import Ride
from .serializers import RideSerializer


# --- Web Views ---

class RideSearchView(ListView):
    model = Ride
    template_name = 'rides/search.html'
    context_object_name = 'rides'

    def get_queryset(self):
        queryset = Ride.objects.filter(status='active').select_related('driver')
        
        origin = self.request.GET.get('origin', '').strip()
        destination = self.request.GET.get('destination', '').strip()
        date_str = self.request.GET.get('date', '').strip()
        seats_str = self.request.GET.get('seats', '').strip()

        if origin:
            queryset = queryset.filter(origin__icontains=origin)
        if destination:
            queryset = queryset.filter(destination__icontains=destination)
        if date_str:
            try:
                search_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(departure_time__date=search_date)
            except ValueError:
                pass
        if seats_str and seats_str.isdigit():
            queryset = queryset.filter(available_seats__gte=int(seats_str))

        return queryset.order_by('departure_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rides = list(context['rides'])
        
        origin = self.request.GET.get('origin', '').strip()
        destination = self.request.GET.get('destination', '').strip()
        date_str = self.request.GET.get('date', '').strip()
        seats_str = self.request.GET.get('seats', '1').strip()

        context['search_origin'] = origin
        context['search_destination'] = destination
        context['search_date'] = date_str
        context['search_seats'] = seats_str
        context['total_rides_count'] = len(rides)

        # Dynamic Heading
        if origin and destination:
            context['page_heading'] = f"Carpool {origin.title()} > {destination.title()}"
        elif origin:
            context['page_heading'] = f"Carpool Rides from {origin.title()}"
        elif destination:
            context['page_heading'] = f"Carpool Rides to {destination.title()}"
        else:
            context['page_heading'] = "Available Carpool Rides"

        # Highlight cheapest & earliest rides
        if rides:
            cheapest_ride = min(rides, key=lambda r: r.price_per_seat)
            earliest_ride = min(rides, key=lambda r: r.departure_time)
            
            for ride in rides:
                ride.is_cheapest = (ride.id == cheapest_ride.id)
                ride.is_earliest = (ride.id == earliest_ride.id and not ride.is_cheapest)

        # Generate next 7 days date pills with starting prices
        today = timezone.now().date()
        date_pills = []
        for i in range(7):
            day_date = today + datetime.timedelta(days=i)
            day_rides = Ride.objects.filter(status='active', departure_time__date=day_date)
            if origin:
                day_rides = day_rides.filter(origin__icontains=origin)
            if destination:
                day_rides = day_rides.filter(destination__icontains=destination)
            
            min_price_agg = day_rides.aggregate(min_price=Min('price_per_seat'))
            min_price = min_price_agg['min_price']
            
            date_pills.append({
                'date_str': day_date.strftime('%Y-%m-%d'),
                'label': day_date.strftime('%a, %d %b'),
                'min_price': min_price,
                'is_selected': (date_str == day_date.strftime('%Y-%m-%d'))
            })
            
        context['date_pills'] = date_pills
        return context


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

    def get_queryset(self):
        return Ride.objects.select_related('driver').prefetch_related('bookings__passenger')


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
