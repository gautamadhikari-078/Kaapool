import os
import json
import logging
import datetime
import math
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.db.models import Min, Q, Count, Case, When, Value, IntegerField
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import viewsets, permissions
from .models import Ride, ReturnRideReminder
from .serializers import RideSerializer
from .services.routing import (
    get_ors_directions,
    geocode_location,
    reverse_geocode_location
)
from .services.return_ride_service import (
    validate_return_ride_timing,
    trigger_return_ride_reminder_if_needed,
    handle_ride_cancelled,
    schedule_return_ride_later,
    skip_return_ride,
    create_return_ride
)


logger = logging.getLogger(__name__)


# --- Web Views ---

class RideSearchView(ListView):
    model = Ride
    template_name = 'rides/search.html'
    context_object_name = 'rides'

    def get_queryset(self):
        queryset = Ride.objects.filter(status__in=['scheduled', 'active', 'in_progress']).select_related('driver')
        
        origin = self.request.GET.get('origin', '').strip()
        destination = self.request.GET.get('destination', '').strip()
        date_str = self.request.GET.get('date', '').strip()
        seats_str = self.request.GET.get('seats', '').strip()

        if origin:
            queryset = queryset.filter(Q(origin__icontains=origin) | Q(pickup_address__icontains=origin))
        if destination:
            queryset = queryset.filter(Q(destination__icontains=destination) | Q(drop_address__icontains=destination))
        if date_str:
            try:
                search_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(departure_datetime__date=search_date)
            except ValueError:
                pass
        if seats_str and seats_str.isdigit():
            queryset = queryset.filter(available_seats__gte=int(seats_str))

        return queryset.order_by('departure_datetime')

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

        if origin and destination:
            context['page_heading'] = f"Carpool {origin.title()} > {destination.title()}"
        elif origin:
            context['page_heading'] = f"Carpool Rides from {origin.title()}"
        elif destination:
            context['page_heading'] = f"Carpool Rides to {destination.title()}"
        else:
            context['page_heading'] = "Available Carpool Rides"

        if rides:
            cheapest_ride = min(rides, key=lambda r: r.price_per_seat)
            earliest_ride = min(rides, key=lambda r: r.departure_datetime)
            
            for ride in rides:
                ride.is_cheapest = (ride.id == cheapest_ride.id)
                ride.is_earliest = (ride.id == earliest_ride.id and not ride.is_cheapest)

        today = timezone.now().date()
        date_pills = []
        for i in range(7):
            day_date = today + datetime.timedelta(days=i)
            day_rides = Ride.objects.filter(status__in=['scheduled', 'active', 'in_progress'], departure_datetime__date=day_date)
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
    fields = [
        'origin', 'destination', 'pickup_point', 'departure_datetime',
        'available_seats', 'price_per_seat', 'vehicle_info', 'notes',
        'pickup_address', 'pickup_latitude', 'pickup_longitude', 'pickup_place_id',
        'drop_address', 'drop_latitude', 'drop_longitude', 'drop_place_id',
        'route_geometry', 'estimated_distance_km', 'estimated_duration_mins'
    ]
    success_url = reverse_lazy('rides:my_rides')

    def form_valid(self, form):
        form.instance.driver = self.request.user
        form.instance.status = 'scheduled'
        if not form.instance.departure_datetime and self.request.POST.get('departure_time'):
            form.instance.departure_datetime = self.request.POST.get('departure_time')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        dup_id = self.request.GET.get('duplicate')
        ret_id = self.request.GET.get('return_from')

        if dup_id:
            try:
                ride = Ride.objects.get(id=dup_id, driver=self.request.user)
                initial.update({
                    'origin': ride.origin,
                    'destination': ride.destination,
                    'pickup_address': ride.pickup_address or ride.origin,
                    'drop_address': ride.drop_address or ride.destination,
                    'available_seats': ride.available_seats,
                    'price_per_seat': ride.price_per_seat,
                    'vehicle_info': ride.vehicle_info,
                    'notes': ride.notes,
                })
            except Ride.DoesNotExist:
                pass
        elif ret_id:
            try:
                ride = Ride.objects.get(id=ret_id, driver=self.request.user)
                initial.update({
                    'origin': ride.destination,
                    'destination': ride.origin,
                    'pickup_address': ride.drop_address or ride.destination,
                    'drop_address': ride.pickup_address or ride.origin,
                    'available_seats': ride.available_seats,
                    'price_per_seat': ride.price_per_seat,
                    'vehicle_info': ride.vehicle_info,
                    'notes': ride.notes,
                })
            except Ride.DoesNotExist:
                pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.conf import settings
        context['mapbox_access_token'] = getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or os.getenv('MAPBOX_ACCESS_TOKEN', '')
        return context

    def form_valid(self, form):
        form.instance.driver = self.request.user
        form.instance.pickup_point = form.instance.pickup_address or form.instance.origin

        # Extract POST parameters for coordinates & route geometry
        post_data = self.request.POST
        pickup_lat = post_data.get('pickup_latitude')
        pickup_lng = post_data.get('pickup_longitude')

        drop_lat = post_data.get('drop_latitude')
        drop_lng = post_data.get('drop_longitude')

        route_geom_str = post_data.get('route_geometry')
        est_dist = post_data.get('estimated_distance_km')
        est_dur = post_data.get('estimated_duration_mins')


        # Geocode origin/destination if coordinates missing
        if not pickup_lat or not pickup_lng:
            orig_geo = geocode_location(form.instance.origin or form.instance.pickup_point)
            if orig_geo:
                form.instance.pickup_latitude = orig_geo[0]['lat']
                form.instance.pickup_longitude = orig_geo[0]['lng']
                form.instance.pickup_address = orig_geo[0]['display_name']
        else:
            form.instance.pickup_latitude = float(pickup_lat)
            form.instance.pickup_longitude = float(pickup_lng)
            form.instance.pickup_address = post_data.get('pickup_address', form.instance.origin)

        if not drop_lat or not drop_lng:
            dest_geo = geocode_location(form.instance.destination)
            if dest_geo:
                form.instance.drop_latitude = dest_geo[0]['lat']
                form.instance.drop_longitude = dest_geo[0]['lng']
                form.instance.drop_address = dest_geo[0]['display_name']
        else:
            form.instance.drop_latitude = float(drop_lat)
            form.instance.drop_longitude = float(drop_lng)
            form.instance.drop_address = post_data.get('drop_address', form.instance.destination)

        # Parse route geometry or calculate via ORS
        if route_geom_str:
            try:
                form.instance.route_geometry = json.loads(route_geom_str)
            except Exception:
                pass

        if not form.instance.route_geometry and form.instance.pickup_longitude and form.instance.drop_longitude:
            coords = [
                [form.instance.pickup_longitude, form.instance.pickup_latitude],
                [form.instance.drop_longitude, form.instance.drop_latitude]
            ]
            ors_res = get_ors_directions(coords)
            if ors_res.get('success'):
                form.instance.route_geometry = ors_res.get('geometry')
                form.instance.estimated_distance_km = ors_res.get('distance_km')
                form.instance.estimated_duration_mins = ors_res.get('duration_mins')

        if est_dist:
            form.instance.estimated_distance_km = float(est_dist)
        if est_dur:
            form.instance.estimated_duration_mins = int(float(est_dur))

        response = super().form_valid(form)

        # Trigger Transactional Email for Ride Creation
        try:
            from apps.core.email_service import EmailService
            EmailService.send_ride_created_email(self.request.user, self.object)
        except Exception as e:
            logger.error(f"Error triggering ride created email: {e}")

        return response

    def get_success_url(self):
        if getattr(self.object, 'is_return_ride', False):
            return reverse('rides:my_rides')
        return reverse('rides:return_ride_prompt', kwargs={'pk': self.object.pk})


class RideDetailView(DetailView):
    model = Ride
    template_name = 'rides/detail.html'
    context_object_name = 'ride'

    def get_queryset(self):
        return Ride.objects.select_related('driver').prefetch_related('bookings__passenger')

    def get_object(self, queryset=None):
        ride = super().get_object(queryset)
        today = timezone.localdate()
        now = timezone.now()
        # Auto-complete or expire past rides if date has passed
        if ride.departure_datetime.date() < today:
            if ride.status == 'in_progress':
                ride.status = 'completed'
                ride.completed_at = now
                ride.save(update_fields=['status', 'completed_at'])
                ride.bookings.filter(status='confirmed').update(status='completed')
            elif ride.status in ['scheduled', 'active']:
                ride.status = 'expired'
                ride.save(update_fields=['status'])
                ride.bookings.filter(status__in=['pending', 'confirmed']).update(status='cancelled')
        return ride

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ride = self.object
        context['is_driver'] = (self.request.user.is_authenticated and self.request.user == ride.driver)
        
        # Check if user is a booked passenger
        is_passenger = False
        passenger_booking = None
        if self.request.user.is_authenticated:
            passenger_booking = ride.bookings.filter(passenger=self.request.user, status__in=['confirmed', 'pending']).first()
            is_passenger = (passenger_booking is not None)
        context['is_passenger'] = is_passenger
        context['passenger_booking'] = passenger_booking
        return context


class MyRidesView(LoginRequiredMixin, ListView):
    model = Ride
    template_name = 'rides/my_rides.html'
    context_object_name = 'offered_rides'
    paginate_by = 10

    def auto_sync_past_rides(self, user):
        """
        Auto-updates rides whose departure date is in the past (< today):
        - In-progress rides whose date has passed -> 'completed'
        - Scheduled/active rides whose date has passed -> 'expired'
        """
        today = timezone.localdate()
        now = timezone.now()

        # Update past in-progress rides to completed
        past_in_prog = Ride.objects.filter(
            driver=user,
            status='in_progress',
            departure_datetime__date__lt=today
        )
        for r in past_in_prog:
            r.status = 'completed'
            r.completed_at = now
            r.save(update_fields=['status', 'completed_at'])
            r.bookings.filter(status='confirmed').update(status='completed')

        # Update past unstarted scheduled rides to expired
        past_sched = Ride.objects.filter(
            driver=user,
            status__in=['scheduled', 'active'],
            departure_datetime__date__lt=today
        )
        for r in past_sched:
            r.status = 'expired'
            r.save(update_fields=['status'])
            r.bookings.filter(status__in=['pending', 'confirmed']).update(status='cancelled')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.auto_sync_past_rides(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)

        queryset = Ride.objects.filter(driver=user).select_related('driver').prefetch_related('bookings', 'bookings__passenger')

        # 1. Tabs Filtering (All, Upcoming, In progress, Completed, Cancelled)
        status_filter = self.request.GET.get('status', 'all').strip().lower()
        if not status_filter:
            status_filter = 'all'

        tab_default_sort = 'default'
        if status_filter == 'upcoming':
            # Upcoming: status=scheduled AND departure in future, sorted soonest first
            queryset = queryset.filter(
                Q(status='scheduled') | Q(status='active'),
                departure_datetime__gt=now
            )
            tab_default_sort = 'soonest'
        elif status_filter == 'in_progress':
            queryset = queryset.filter(status='in_progress')
            tab_default_sort = 'latest'
        elif status_filter == 'completed':
            # Completed: completed + expired, newest first
            queryset = queryset.filter(status__in=['completed', 'expired'])
            tab_default_sort = 'latest'
        elif status_filter == 'cancelled':
            # Cancelled: newest first
            queryset = queryset.filter(status='cancelled')
            tab_default_sort = 'latest'
        else:
            # All: upcoming first, then past
            status_filter = 'all'
            tab_default_sort = 'all_default'

        # 2. Date Chips: Today, Tomorrow, This week (combine with tab)
        date_filter = self.request.GET.get('date', '').strip().lower()
        if date_filter == 'today':
            queryset = queryset.filter(departure_datetime__date=today)
        elif date_filter == 'tomorrow':
            queryset = queryset.filter(departure_datetime__date=tomorrow)
        elif date_filter == 'this_week':
            queryset = queryset.filter(departure_datetime__date__range=[week_start, week_end])

        # 3. Sort dropdown ("Soonest first" / "Latest first") that overrides tab default
        sort_filter = self.request.GET.get('sort', '').strip().lower()
        if sort_filter == 'soonest':
            queryset = queryset.order_by('departure_datetime')
        elif sort_filter == 'latest':
            queryset = queryset.order_by('-departure_datetime')
        else:
            if tab_default_sort == 'soonest':
                queryset = queryset.order_by('departure_datetime')
            elif tab_default_sort == 'latest':
                queryset = queryset.order_by('-departure_datetime')
            else:
                # All default: upcoming first (soonest first), then past
                is_past_expr = Case(
                    When(departure_datetime__lt=now, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
                queryset = queryset.annotate(is_past=is_past_expr).order_by('is_past', 'departure_datetime')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()
        today = timezone.localdate()
        tomorrow = today + datetime.timedelta(days=1)

        # Compute all tab counts in a single aggregate query
        tab_counts = Ride.objects.filter(driver=user).aggregate(
            all_count=Count('id'),
            upcoming_count=Count('id', filter=(Q(status='scheduled') | Q(status='active')) & Q(departure_datetime__gt=now)),
            in_progress_count=Count('id', filter=Q(status='in_progress')),
            completed_count=Count('id', filter=Q(status__in=['completed', 'expired'])),
            cancelled_count=Count('id', filter=Q(status='cancelled'))
        )

        current_status = self.request.GET.get('status', 'all').strip().lower() or 'all'
        current_date = self.request.GET.get('date', '').strip().lower()
        current_sort = self.request.GET.get('sort', '').strip().lower()

        context['total_count'] = tab_counts.get('all_count', 0)
        context['all_count'] = tab_counts.get('all_count', 0)
        context['upcoming_count'] = tab_counts.get('upcoming_count', 0)
        context['in_progress_count'] = tab_counts.get('in_progress_count', 0)
        context['completed_count'] = tab_counts.get('completed_count', 0)
        context['cancelled_count'] = tab_counts.get('cancelled_count', 0)

        context['current_status'] = current_status
        context['current_date'] = current_date
        context['current_sort'] = current_sort
        context['today'] = today
        context['tomorrow'] = tomorrow
        context['now'] = now

        # Group page rides by date for header rendering ("Today", "Tomorrow", etc.)
        rides_page = context.get('page_obj')
        rides_list = list(rides_page.object_list) if rides_page else list(context.get('offered_rides', []))

        user_tz = timezone.get_current_timezone()
        grouped_dict = {}
        for r in rides_list:
            r_date = r.departure_datetime.astimezone(user_tz).date()
            if r_date not in grouped_dict:
                if r_date == today:
                    label = "Today"
                elif r_date == tomorrow:
                    label = "Tomorrow"
                else:
                    label = r_date.strftime("%a, %d %b")
                grouped_dict[r_date] = {'date': r_date, 'label': label, 'rides': []}
            grouped_dict[r_date]['rides'].append(r)

        context['grouped_rides'] = list(grouped_dict.values())

        # Build query string preserving all params except page for pagination links
        params = self.request.GET.copy()
        if 'page' in params:
            del params['page']
        context['query_params_no_page'] = params.urlencode()

        return context


class RidePublicationView(LoginRequiredMixin, DetailView):
    model = Ride
    template_name = 'rides/publication.html'
    context_object_name = 'ride'

    def get_queryset(self):
        return Ride.objects.filter(driver=self.request.user)


# --- ORS Routing & Geocoding Backend APIs ---

class RouteCalculateAPIView(View):
    """
    Backend proxy for OpenRouteService Directions API.
    NEVER exposes ORS API key to frontend JS.
    Accepts JSON: {"coordinates": [[lng1, lat1], [lng2, lat2], ...]}
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode('utf-8'))
            coords = data.get('coordinates', [])
            if not coords or len(coords) < 2:
                return JsonResponse({'success': False, 'error': 'At least 2 coordinate points required.'}, status=400)

            result = get_ors_directions(coords)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"Route calculation API error: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class GeocodeAPIView(View):
    """
    Backend proxy for location geocoding / search in India using ORS / Nominatim.
    """
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse([], safe=False)

        results = geocode_location(query)
        return JsonResponse(results, safe=False)


class ReverseGeocodeAPIView(View):
    """
    Backend proxy for reverse geocoding lat/lng to street address.
    """
    def get(self, request, *args, **kwargs):
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        if not lat or not lng:
            return JsonResponse({'error': 'lat and lng parameters required'}, status=400)

        res = reverse_geocode_location(float(lat), float(lng))
        return JsonResponse(res)






# --- Live Ride Tracking Actions ---

class StartRideView(LoginRequiredMixin, View):
    """
    Driver starts ride -> status becomes IN_PROGRESS, started_at set.
    Supports both POST and GET.
    """
    def get(self, request, pk, *args, **kwargs):
        return self._start(request, pk)

    def post(self, request, pk, *args, **kwargs):
        return self._start(request, pk)

    def _start(self, request, pk):
        ride = get_object_or_404(Ride, id=pk, driver=request.user)
        if ride.status != 'in_progress':
            ride.status = 'in_progress'
            ride.started_at = timezone.now()
            ride.save(update_fields=['status', 'started_at'])
            messages.success(request, f"Ride to {ride.destination} has been started.")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': True, 'status': 'in_progress', 'started_at': ride.started_at.isoformat()})
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('rides:detail', pk=ride.id)


class CancelRideView(LoginRequiredMixin, View):
    """
    Driver cancels an offered ride (from Manage ride or my-rides list).
    Supports both POST and GET.
    """
    def get(self, request, pk, *args, **kwargs):
        return self._cancel(request, pk)

    def post(self, request, pk, *args, **kwargs):
        return self._cancel(request, pk)

    def _cancel(self, request, pk):
        ride = get_object_or_404(Ride, id=pk, driver=request.user)
        if ride.status not in ['completed', 'cancelled']:
            ride.status = 'cancelled'
            ride.save(update_fields=['status'])
            handle_ride_cancelled(ride)
            
            # Fetch active passengers before status update
            active_bookings = list(ride.bookings.filter(status__in=['pending', 'confirmed']).select_related('passenger'))
            ride.bookings.filter(status__in=['pending', 'confirmed']).update(status='cancelled')
            
            # Send cancellation notifications via centralized EmailService (Brevo)
            try:
                from apps.core.email_service import EmailService
                EmailService.send_ride_cancelled_email(request.user, ride, is_driver=True)
                for booking in active_bookings:
                    if booking.passenger and booking.passenger.email:
                        EmailService.send_ride_cancelled_email(booking.passenger, ride, is_driver=False)
            except Exception as email_err:
                logger.error(f"Failed to send ride cancellation email: {email_err}")

            messages.success(request, f"Ride to {ride.destination} has been cancelled.")
        else:
            messages.info(request, f"Ride is already {ride.status}.")

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(f"{reverse('rides:my_rides')}?status=cancelled")


class CompleteRideView(LoginRequiredMixin, View):
    """
    Driver completes ride -> status becomes COMPLETED, completed_at set.
    Supports both POST and GET.
    """
    def get(self, request, pk, *args, **kwargs):
        return self._complete(request, pk)

    def post(self, request, pk, *args, **kwargs):
        return self._complete(request, pk)

    def _complete(self, request, pk):
        ride = get_object_or_404(Ride, id=pk, driver=request.user)
        if ride.status != 'completed':
            ride.status = 'completed'
            ride.completed_at = timezone.now()
            ride.save(update_fields=['status', 'completed_at'])
            ride.bookings.filter(status='confirmed').update(status='completed')
            trigger_return_ride_reminder_if_needed(ride)
            messages.success(request, f"Ride to {ride.destination} has been marked as completed.")
        else:
            messages.info(request, "Ride is already completed.")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'success': True, 'status': 'completed', 'completed_at': ride.completed_at.isoformat()})
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(f"{reverse('rides:my_rides')}?status=completed")


class UpdateLocationAPIView(LoginRequiredMixin, View):
    """
    Driver posts live GPS coordinates {lat, lng, timestamp}.
    Throttles ORS remaining distance & ETA calculation.
    """
    def post(self, request, pk, *args, **kwargs):
        ride = get_object_or_404(Ride, id=pk, driver=request.user)
        try:
            data = json.loads(request.body.decode('utf-8'))
            lat = float(data.get('lat'))
            lng = float(data.get('lng'))
            timestamp = data.get('timestamp') or timezone.now().isoformat()

            now = timezone.now()
            ride.current_driver_lat = lat
            ride.current_driver_lng = lng

            if not isinstance(ride.actual_gps_track, list):
                ride.actual_gps_track = []
            ride.actual_gps_track.append({
                'lat': lat,
                'lng': lng,
                'timestamp': timestamp
            })

            # Throttled ETA calculation: recalculate every 15 sec
            should_recalc = False
            if not ride.last_location_update or (now - ride.last_location_update).total_seconds() >= 15:
                should_recalc = True

            if should_recalc and ride.drop_latitude and ride.drop_longitude:
                try:
                    ors_res = get_ors_directions([[lng, lat], [ride.drop_longitude, ride.drop_latitude]])
                    if ors_res.get('success'):
                        ride.estimated_distance_km = ors_res.get('distance_km')
                        ride.estimated_duration_mins = ors_res.get('duration_mins')
                except Exception as ex:
                    logger.warning(f"Error recalculating ETA: {ex}")

            ride.last_location_update = now
            ride.save(update_fields=[
                'current_driver_lat', 'current_driver_lng', 'actual_gps_track',
                'last_location_update', 'estimated_distance_km', 'estimated_duration_mins'
            ])

            return JsonResponse({
                'success': True,
                'status': ride.status,
                'remaining_distance_km': ride.estimated_distance_km,
                'remaining_duration_mins': ride.estimated_duration_mins
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class LiveStatusAPIView(View):
    """
    Passenger / live map subscriber gets real-time ride tracking status.
    """
    def get(self, request, pk, *args, **kwargs):
        ride = get_object_or_404(Ride, id=pk)
        return JsonResponse({
            'ride_id': ride.id,
            'status': ride.status,
            'driver_name': ride.driver.get_full_name() or ride.driver.username,
            'driver_lat': ride.current_driver_lat,
            'driver_lng': ride.current_driver_lng,
            'pickup_lat': ride.pickup_latitude,
            'pickup_lng': ride.pickup_longitude,
            'pickup_address': ride.pickup_address or ride.pickup_point or ride.origin,
            'drop_lat': ride.drop_latitude,
            'drop_lng': ride.drop_longitude,
            'drop_address': ride.drop_address or ride.destination,
            'route_geometry': ride.route_geometry,
            'remaining_distance_km': ride.estimated_distance_km,
            'remaining_duration_mins': ride.estimated_duration_mins,
            'started_at': ride.started_at.isoformat() if ride.started_at else None,
            'completed_at': ride.completed_at.isoformat() if ride.completed_at else None,
            'last_location_update': ride.last_location_update.isoformat() if ride.last_location_update else None,
            'actual_gps_track': ride.actual_gps_track or []
        })


# --- Spatial and Route Comparison Helpers (Turf.js geometry logic) ---

def _haversine_distance(p1, p2):
    """Calculate distance in meters between two [lon, lat] points using haversine formula."""
    lon1, lat1 = p1
    lon2, lat2 = p2
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _sample_points_along_route(coords, num_points=50):
    """
    Sample num_points evenly spaced points along a GeoJSON coordinates list (Turf.js turf.along equivalent).
    """
    if not coords:
        return []
    if len(coords) == 1 or num_points <= 1:
        return [coords[0]] * num_points

    cum_dists = [0.0]
    for i in range(len(coords) - 1):
        d = _haversine_distance(coords[i], coords[i + 1])
        cum_dists.append(cum_dists[-1] + d)

    total_dist = cum_dists[-1]
    if total_dist == 0:
        return [coords[0]] * num_points

    step = total_dist / float(num_points - 1)
    sampled = []
    seg_idx = 0
    num_coords = len(coords)

    for k in range(num_points):
        target_d = k * step
        while seg_idx < num_coords - 2 and cum_dists[seg_idx + 1] < target_d:
            seg_idx += 1
        d0 = cum_dists[seg_idx]
        d1 = cum_dists[seg_idx + 1]
        seg_len = d1 - d0
        if seg_len <= 0:
            sampled.append(coords[seg_idx])
        else:
            t = max(0.0, min(1.0, (target_d - d0) / seg_len))
            lon = coords[seg_idx][0] + t * (coords[seg_idx + 1][0] - coords[seg_idx][0])
            lat = coords[seg_idx][1] + t * (coords[seg_idx + 1][1] - coords[seg_idx][1])
            sampled.append([lon, lat])

    return sampled


def _point_to_linestring_min_distance(point, coords, threshold_meters=500.0):
    """
    Calculate minimum distance in meters from point [lon, lat] to a LineString coordinates list
    (Turf.js turf.pointToLineDistance equivalent).
    Early exits if any segment is within threshold_meters.
    """
    lon_q, lat_q = point
    R = 6371000.0
    lat_rad = math.radians(lat_q)
    deg_lat_m = (math.pi / 180.0) * R
    deg_lon_m = deg_lat_m * math.cos(lat_rad)

    lat_buffer = threshold_meters / deg_lat_m if deg_lat_m > 0 else 0.005
    lon_buffer = threshold_meters / deg_lon_m if deg_lon_m > 0 else 0.005
    threshold_sq = threshold_meters * threshold_meters

    min_dist_sq = float('inf')

    for i in range(len(coords) - 1):
        a = coords[i]
        b = coords[i + 1]

        # Fast bounding box check
        min_lat = min(a[1], b[1]) - lat_buffer
        max_lat = max(a[1], b[1]) + lat_buffer
        if lat_q < min_lat or lat_q > max_lat:
            continue
        min_lon = min(a[0], b[0]) - lon_buffer
        max_lon = max(a[0], b[0]) + lon_buffer
        if lon_q < min_lon or lon_q > max_lon:
            continue

        xa = (a[0] - lon_q) * deg_lon_m
        ya = (a[1] - lat_q) * deg_lat_m
        xb = (b[0] - lon_q) * deg_lon_m
        yb = (b[1] - lat_q) * deg_lat_m

        dx = xb - xa
        dy = yb - ya
        seg_sq = dx * dx + dy * dy
        if seg_sq == 0:
            dist_sq = xa * xa + ya * ya
        else:
            t = max(0.0, min(1.0, (-xa * dx - ya * dy) / seg_sq))
            xc = xa + t * dx
            yc = ya + t * dy
            dist_sq = xc * xc + yc * yc

        if dist_sq <= threshold_sq:
            return math.sqrt(dist_sq)
        if dist_sq < min_dist_sq:
            min_dist_sq = dist_sq

    return math.sqrt(min_dist_sq)


def isSameRoute(route1, route2) -> bool:
    """
    Helper to check if two routes are duplicates:
    Two routes are duplicates if at least 90% of 50 evenly spaced points on one
    lie within 500 m of the other (implementing Turf.js geometry principles).
    Accepts route dicts or GeoJSON geometries.
    """
    def extract_coords(r):
        if isinstance(r, dict):
            if 'geometry' in r and isinstance(r['geometry'], dict):
                return r['geometry'].get('coordinates', [])
            elif 'coordinates' in r:
                return r.get('coordinates', [])
        elif isinstance(r, (list, tuple)):
            return r
        return []

    coords1 = extract_coords(route1)
    coords2 = extract_coords(route2)

    if not coords1 or not coords2:
        return False

    def check_directed(c_src, c_target):
        sample_pts = _sample_points_along_route(c_src, num_points=50)
        if not sample_pts:
            return False
        close_pts_count = sum(
            1 for pt in sample_pts
            if _point_to_linestring_min_distance(pt, c_target, threshold_meters=500.0) <= 500.0
        )
        return (close_pts_count / float(len(sample_pts))) >= 0.90

    return check_directed(coords1, coords2) or check_directed(coords2, coords1)


class MapboxRoutesAPIView(View):
    """
    GET /api/routes?originLat=...&originLng=...&destLat=...&destLng=...
    Makes 3 parallel calls to Mapbox Directions API:
      (1) alternatives=true
      (2) exclude=toll
      (3) exclude=motorway
    Ignores any call that fails or returns no route, as long as at least one route is found.
    Merges routes, removes duplicates with isSameRoute, sorts by duration, and returns at most 4 routes.
    Caches the result by rounded origin+destination for 1 hour.
    """
    def get(self, request, *args, **kwargs):
        origin_lat_raw = request.GET.get('originLat')
        origin_lng_raw = request.GET.get('originLng')
        dest_lat_raw = request.GET.get('destLat')
        dest_lng_raw = request.GET.get('destLng')

        if not all([origin_lat_raw, origin_lng_raw, dest_lat_raw, dest_lng_raw]):
            return JsonResponse({'error': 'Missing required query parameters: originLat, originLng, destLat, destLng.'}, status=400)

        try:
            origin_lat = float(origin_lat_raw)
            origin_lng = float(origin_lng_raw)
            dest_lat = float(dest_lat_raw)
            dest_lng = float(dest_lng_raw)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid latitude or longitude format.'}, status=400)

        # Cache key rounded to 4 decimal places (~11m precision) for 1 hour
        cache_key = f"mapbox_routes_{round(origin_lat, 4)}_{round(origin_lng, 4)}_{round(dest_lat, 4)}_{round(dest_lng, 4)}"
        cached_routes = cache.get(cache_key)
        if cached_routes is not None:
            return JsonResponse(cached_routes, safe=False)

        from django.conf import settings
        mapbox_token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or os.getenv('MAPBOX_ACCESS_TOKEN', '')

        # Parallel calls: (1) alternatives=true, (2) exclude=toll, (3) exclude=motorway
        call_params = ['alternatives=true', 'exclude=toll', 'exclude=motorway']

        def fetch_mapbox_route(param_str):
            url = (
                f"https://api.mapbox.com/directions/v5/mapbox/driving/"
                f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
                f"?{param_str}&geometries=geojson&overview=full&access_token={mapbox_token}"
            )
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        if data.get('code') == 'Ok':
                            routes = data.get('routes', [])
                            for r in routes:
                                if param_str == 'exclude=toll':
                                    r['_hasTolls'] = False
                            return routes
            except Exception as e:
                logger.warning(f"Mapbox directions call ({param_str}) error: {e}")
            return []

        all_routes = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_param = {executor.submit(fetch_mapbox_route, p): p for p in call_params}
            for future in as_completed(future_to_param):
                param = future_to_param[future]
                try:
                    routes = future.result()
                    if routes:
                        all_routes.extend(routes)
                except Exception as e:
                    logger.warning(f"Mapbox directions call with {param} failed: {e}")

        if not all_routes:
            return JsonResponse({'error': 'No route found between the specified locations.'}, status=404)

        # Remove duplicate routes using isSameRoute helper
        unique_routes = []
        for r in all_routes:
            if not any(isSameRoute(r, u) for u in unique_routes):
                unique_routes.append(r)

        # Sort by duration ascending
        unique_routes.sort(key=lambda r: r.get('duration', 0))

        # Return at most 4 routes formatted cleanly
        clean_routes = []
        for idx, route in enumerate(unique_routes[:4]):
            dist_meters = route.get('distance', 0)
            dur_seconds = route.get('duration', 0)
            geometry = route.get('geometry', {})
            legs = route.get('legs', [])
            summary = legs[0].get('summary', '') if legs else ''
            has_tolls = route.get('_hasTolls', True)

            clean_routes.append({
                'id': f'route_{idx}',
                'distanceKm': round(dist_meters / 1000),
                'durationMin': round(dur_seconds / 60),
                'geometry': geometry,
                'summary': summary,
                'hasTolls': has_tolls
            })

        # Cache the result for 1 hour (3600 seconds)
        cache.set(cache_key, clean_routes, timeout=3600)

        return JsonResponse(clean_routes, safe=False)


# --- REST API ViewSets ---

class APIRideViewSet(viewsets.ModelViewSet):
    queryset = Ride.objects.filter(status__in=['active', 'in_progress'])
    serializer_class = RideSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)


# ==========================================================
# RETURN RIDE VIEWS & APIS
# ==========================================================

class ReturnRidePromptView(LoginRequiredMixin, View):
    """
    Step 2: Post-ride-creation prompt screen.
    Displays:
    - Original ride reference card (From, To, Date, Time)
    - Option 1: Make Return Ride (Immediate flow)
    - Option 2: Schedule for Later (Reminder after original ride completed)
    - Option 3: Skip (Navigate directly to My Rides)
    """
    template_name = 'rides/return_ride_prompt.html'

    def get(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        if ride.driver != request.user and not request.user.is_staff:
            messages.error(request, "You do not have permission to access this ride.")
            return redirect('rides:my_rides')

        if ride.is_return_ride:
            return redirect('rides:my_rides')

        if ride.has_return_ride:
            messages.info(request, f"A return ride ({ride.return_ride.origin} → {ride.return_ride.destination}) already exists for this trip.")
            return redirect('rides:detail', pk=ride.return_ride.id)

        # Mark reminder as OPENED if opened from notification
        reminder = ride.reminders.filter(status='TRIGGERED').first()
        if reminder:
            reminder.status = 'OPENED'
            reminder.save(update_fields=['status'])

        return render(request, self.template_name, {'original_ride': ride})

    def post(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        if ride.driver != request.user and not request.user.is_staff:
            messages.error(request, "You do not have permission to modify this ride.")
            return redirect('rides:my_rides')

        action = request.POST.get('action')
        if action == 'make_now':
            return redirect('rides:return_ride_create', pk=ride.pk)
        elif action == 'schedule_later':
            try:
                schedule_return_ride_later(ride, request.user)
                messages.success(request, f"Scheduled for later! We will remind you to create a return ride once your trip to {ride.destination} is completed.")
            except Exception as e:
                messages.warning(request, str(e))
            return redirect('rides:my_rides')
        elif action == 'skip':
            skip_return_ride(ride, request.user)
            return redirect('rides:my_rides')
        else:
            return redirect('rides:my_rides')


class ReturnRideCreateView(LoginRequiredMixin, View):
    """
    Step 3: Return Ride Creation Flow.
    Pre-fills reversed origin & destination, pre-fills fare, seats, vehicle.
    Enforces strict departure timing validation (> original ride departure).
    Prevents duplicate return ride creation.
    """
    template_name = 'rides/return_ride_create.html'

    def get(self, request, pk):
        original_ride = get_object_or_404(Ride, pk=pk)
        if original_ride.driver != request.user and not request.user.is_staff:
            messages.error(request, "You do not have permission to create a return ride for this trip.")
            return redirect('rides:my_rides')

        if original_ride.is_return_ride:
            messages.warning(request, "Cannot create a return ride for a ride that is already a return ride.")
            return redirect('rides:my_rides')

        if original_ride.has_return_ride:
            messages.warning(request, f"A return ride already exists for this trip (#{original_ride.return_ride.id}).")
            return redirect('rides:detail', pk=original_ride.return_ride.id)

        # Default suggested return departure time: original departure + estimated duration + 2 hours (or departure + 4 hours)
        suggested_delta = datetime.timedelta(hours=4)
        if original_ride.estimated_duration_mins:
            suggested_delta = datetime.timedelta(minutes=original_ride.estimated_duration_mins + 120)
        suggested_dt = original_ride.departure_datetime + suggested_delta

        context = {
            'original_ride': original_ride,
            'default_origin': original_ride.destination,
            'default_destination': original_ride.origin,
            'default_pickup_address': original_ride.drop_address or original_ride.destination,
            'default_drop_address': original_ride.pickup_address or original_ride.origin,
            'default_date': suggested_dt.strftime('%Y-%m-%d'),
            'default_time': suggested_dt.strftime('%H:%M'),
            'min_date': original_ride.departure_datetime.strftime('%Y-%m-%d'),
            'default_seats': original_ride.available_seats,
            'default_price': original_ride.price_per_seat,
            'default_vehicle': original_ride.vehicle_info,
            'default_notes': original_ride.notes,
            'mapbox_access_token': getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or os.getenv('MAPBOX_ACCESS_TOKEN', ''),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        original_ride = get_object_or_404(Ride, pk=pk)
        if original_ride.driver != request.user and not request.user.is_staff:
            messages.error(request, "You do not have permission to create a return ride for this trip.")
            return redirect('rides:my_rides')

        if original_ride.is_return_ride:
            messages.error(request, "Cannot create a return ride for a ride that is already a return ride.")
            return redirect('rides:my_rides')

        if original_ride.has_return_ride:
            messages.warning(request, f"A return ride already exists for this trip (#{original_ride.return_ride.id}).")
            return redirect('rides:detail', pk=original_ride.return_ride.id)

        origin = request.POST.get('origin', '').strip() or original_ride.destination
        destination = request.POST.get('destination', '').strip() or original_ride.origin
        date_str = request.POST.get('departure_date', '').strip()
        time_str = request.POST.get('departure_time', '').strip()
        seats_str = request.POST.get('available_seats', '').strip()
        price_str = request.POST.get('price_per_seat', '').strip()
        vehicle_info = request.POST.get('vehicle_info', '').strip() or original_ride.vehicle_info
        notes = request.POST.get('notes', '').strip()

        # Parse departure datetime
        departure_datetime = None
        if date_str and time_str:
            try:
                departure_datetime = timezone.make_aware(
                    datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                )
            except Exception:
                try:
                    departure_datetime = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    pass

        errors = []
        if not departure_datetime:
            errors.append("Please specify a valid departure date and time for the return ride.")
        else:
            try:
                validate_return_ride_timing(original_ride, departure_datetime)
            except Exception as ve:
                errors.append(str(ve))

        try:
            seats = int(seats_str)
            if seats <= 0:
                errors.append("Available seats must be at least 1.")
        except (ValueError, TypeError):
            errors.append("Available seats must be a valid number.")

        try:
            price = float(price_str)
            if price < 0:
                errors.append("Price per seat cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Price per seat must be a valid amount.")

        if errors:
            for err in errors:
                messages.error(request, err)
            context = {
                'original_ride': original_ride,
                'default_origin': origin,
                'default_destination': destination,
                'default_pickup_address': request.POST.get('pickup_address', ''),
                'default_drop_address': request.POST.get('drop_address', ''),
                'default_date': date_str,
                'default_time': time_str,
                'min_date': original_ride.departure_datetime.strftime('%Y-%m-%d'),
                'default_seats': seats_str,
                'default_price': price_str,
                'default_vehicle': vehicle_info,
                'default_notes': notes,
                'mapbox_access_token': getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or os.getenv('MAPBOX_ACCESS_TOKEN', ''),
            }
            return render(request, self.template_name, context)

        # Coordinate handling
        pickup_address = request.POST.get('pickup_address', '').strip() or origin
        drop_address = request.POST.get('drop_address', '').strip() or destination
        
        pickup_lat = request.POST.get('pickup_latitude')
        pickup_lng = request.POST.get('pickup_longitude')
        drop_lat = request.POST.get('drop_latitude')
        drop_lng = request.POST.get('drop_longitude')

        # Fallback to reversed coordinates from original ride if origin/destination match
        if (not pickup_lat or not pickup_lng) and origin == original_ride.destination:
            pickup_lat = original_ride.drop_latitude
            pickup_lng = original_ride.drop_longitude
            if not pickup_address and original_ride.drop_address:
                pickup_address = original_ride.drop_address

        if (not drop_lat or not drop_lng) and destination == original_ride.origin:
            drop_lat = original_ride.pickup_latitude
            drop_lng = original_ride.pickup_longitude
            if not drop_address and original_ride.pickup_address:
                drop_address = original_ride.pickup_address

        # Route geometry
        route_geom_str = request.POST.get('route_geometry')
        route_geometry = None
        if route_geom_str:
            try:
                route_geometry = json.loads(route_geom_str)
            except Exception:
                pass

        if not route_geometry and original_ride.route_geometry and origin == original_ride.destination and destination == original_ride.origin:
            try:
                route_geometry = list(reversed(original_ride.route_geometry))
            except Exception:
                pass

        ride_data = {
            'origin': origin,
            'destination': destination,
            'pickup_point': pickup_address,
            'pickup_address': pickup_address,
            'drop_address': drop_address,
            'pickup_latitude': float(pickup_lat) if pickup_lat else None,
            'pickup_longitude': float(pickup_lng) if pickup_lng else None,
            'drop_latitude': float(drop_lat) if drop_lat else None,
            'drop_longitude': float(drop_lng) if drop_lng else None,
            'route_geometry': route_geometry,
            'estimated_distance_km': original_ride.estimated_distance_km,
            'estimated_duration_mins': original_ride.estimated_duration_mins,
            'departure_datetime': departure_datetime,
            'available_seats': seats,
            'price_per_seat': price,
            'vehicle_info': vehicle_info,
            'notes': notes,
        }

        try:
            return_ride = create_return_ride(original_ride, request.user, ride_data)
            messages.success(request, f"Return ride ({return_ride.origin} → {return_ride.destination}) created successfully!")

            try:
                from apps.core.email_service import EmailService
                EmailService.send_ride_created_email(request.user, return_ride)
            except Exception as e:
                logger.error(f"Error triggering return ride created email: {e}")

            return redirect('rides:my_rides')
        except Exception as ve:
            messages.error(request, str(ve))
            return redirect('rides:return_ride_create', pk=original_ride.pk)


class ScheduleReturnRideLaterView(LoginRequiredMixin, View):
    """
    Direct endpoint for 'Schedule for Later'.
    """
    def post(self, request, pk):
        return self._schedule(request, pk)

    def get(self, request, pk):
        return self._schedule(request, pk)

    def _schedule(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        try:
            schedule_return_ride_later(ride, request.user)
            messages.success(request, f"Scheduled for later! We will remind you to create a return ride once your ride to {ride.destination} is completed.")
        except Exception as ve:
            messages.warning(request, str(ve))
        return redirect('rides:my_rides')


class SkipReturnRideView(LoginRequiredMixin, View):
    """
    Direct endpoint for 'Skip'.
    """
    def post(self, request, pk):
        return self._skip(request, pk)

    def get(self, request, pk):
        return self._skip(request, pk)

    def _skip(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        try:
            skip_return_ride(ride, request.user)
        except Exception:
            pass
        return redirect('rides:my_rides')


# --- REST API Endpoints for Return Ride ---

class ReturnRideOptionsAPIView(LoginRequiredMixin, View):
    """
    GET: Returns pre-filled return ride options and timing constraints.
    """
    def get(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        if ride.driver != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        return JsonResponse({
            'original_ride_id': ride.id,
            'origin': ride.destination,
            'destination': ride.origin,
            'pickup_address': ride.drop_address or ride.destination,
            'drop_address': ride.pickup_address or ride.origin,
            'earliest_allowed_departure': ride.departure_datetime.isoformat(),
            'available_seats': ride.available_seats,
            'price_per_seat': str(ride.price_per_seat),
            'vehicle_info': ride.vehicle_info,
            'has_return_ride': ride.has_return_ride,
            'return_ride_id': ride.return_ride.id if ride.has_return_ride else None,
            'return_ride_status': ride.return_ride_status,
        })


class ReturnRideScheduleAPIView(LoginRequiredMixin, View):
    """
    POST: Schedules return ride reminder for later via API.
    """
    def post(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        try:
            reminder = schedule_return_ride_later(ride, request.user)
            return JsonResponse({
                'success': True,
                'return_ride_status': ride.return_ride_status,
                'reminder_id': reminder.id
            })
        except Exception as ve:
            return JsonResponse({'error': str(ve)}, status=400)


class ReturnRideSkipAPIView(LoginRequiredMixin, View):
    """
    POST: Skips return ride via API.
    """
    def post(self, request, pk):
        ride = get_object_or_404(Ride, pk=pk)
        try:
            skip_return_ride(ride, request.user)
            return JsonResponse({
                'success': True,
                'return_ride_status': ride.return_ride_status
            })
        except Exception as ve:
            return JsonResponse({'error': str(ve)}, status=400)


