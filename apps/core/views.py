from django.shortcuts import render
from django.views.generic import TemplateView
from django.db.models import Count, Min
from apps.rides.models import Ride


class HomeView(TemplateView):
    """Homepage view with dynamic popular carpool routes."""
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        dynamic_routes = []

        try:
            routes_qs = (
                Ride.objects.filter(status='active')
                .values('origin', 'destination')
                .annotate(
                    ride_count=Count('id'),
                    min_price=Min('price_per_seat')
                )
                .order_by('-ride_count')[:6]
            )

            for r in routes_qs:
                dynamic_routes.append({
                    'origin': r['origin'],
                    'destination': r['destination'],
                    'min_price': r['min_price'],
                    'freq_text': f"{r['ride_count']} active ride(s)"
                })

            context['recent_rides'] = (
                Ride.objects
                .filter(status='active')
                .order_by('-created_at')[:4]
            )

        except Exception:
            context['recent_rides'] = []

        default_routes = [
            {'origin': 'Delhi', 'destination': 'Jaipur', 'default_price': 450, 'default_freq': 'Daily 15+ rides'},
            {'origin': 'Gurgaon', 'destination': 'Rohtak', 'default_price': 150, 'default_freq': 'Daily 25+ rides'},
            {'origin': 'Mumbai', 'destination': 'Pune', 'default_price': 350, 'default_freq': 'Daily 30+ rides'},
            {'origin': 'Bangalore', 'destination': 'Mysore', 'default_price': 300, 'default_freq': 'Daily 20+ rides'},
            {'origin': 'Chennai', 'destination': 'Pondicherry', 'default_price': 280, 'default_freq': 'Daily 12+ rides'},
            {'origin': 'Hyderabad', 'destination': 'Vijayawada', 'default_price': 420, 'default_freq': 'Daily 18+ rides'},
        ]

        seen_pairs = {
            (r['origin'].lower(), r['destination'].lower())
            for r in dynamic_routes
        }

        for route in default_routes:
            if len(dynamic_routes) >= 6:
                break

            pair = (
                route['origin'].lower(),
                route['destination'].lower()
            )

            if pair not in seen_pairs:
                dynamic_routes.append({
                    'origin': route['origin'],
                    'destination': route['destination'],
                    'min_price': route['default_price'],
                    'freq_text': route['default_freq']
                })
                seen_pairs.add(pair)

        context['popular_routes'] = dynamic_routes

        return context

class AboutView(TemplateView):
    """About Kaapool page view."""
    template_name = 'core/about.html'


class HowItWorksView(TemplateView):
    """How Kaapool works page view."""
    template_name = 'core/how_it_works.html'


class SafetyView(TemplateView):
    """Safety guidelines page view."""
    template_name = 'core/safety.html'


class ContactView(TemplateView):
    """Contact page view."""
    template_name = 'core/contact.html'
