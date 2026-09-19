from django.urls import path
from .views import (
    RideSearchView, RideCreateView, RideDetailView, MyRidesView, RidePublicationView,
    RouteCalculateAPIView, GeocodeAPIView, ReverseGeocodeAPIView,
    StartRideView, CompleteRideView, CancelRideView, UpdateLocationAPIView, LiveStatusAPIView
)

app_name = 'rides'

urlpatterns = [
    path('', RideSearchView.as_view(), name='list'),
    path('search/', RideSearchView.as_view(), name='search'),
    path('create/', RideCreateView.as_view(), name='create'),
    path('my-rides/', MyRidesView.as_view(), name='my_rides'),

    # ORS Routing & Geocoding APIs
    path('api/route/', RouteCalculateAPIView.as_view(), name='api_route'),
    path('api/geocode/', GeocodeAPIView.as_view(), name='api_geocode'),
    path('api/reverse-geocode/', ReverseGeocodeAPIView.as_view(), name='api_reverse_geocode'),

    # Ride Lifecycle & Live Tracking Endpoints
    path('<int:pk>/', RideDetailView.as_view(), name='detail'),
    path('<int:pk>/publication/', RidePublicationView.as_view(), name='publication'),
    path('<int:pk>/start/', StartRideView.as_view(), name='start'),
    path('<int:pk>/complete/', CompleteRideView.as_view(), name='complete'),
    path('<int:pk>/cancel/', CancelRideView.as_view(), name='cancel'),
    path('<int:pk>/update-location/', UpdateLocationAPIView.as_view(), name='update_location'),
    path('<int:pk>/live-status/', LiveStatusAPIView.as_view(), name='live_status'),
]


