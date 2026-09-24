from django.urls import path
from .views import (
    RideSearchView, RideCreateView, RideDetailView, MyRidesView, RidePublicationView,
    RouteCalculateAPIView, GeocodeAPIView, ReverseGeocodeAPIView,
    StartRideView, CompleteRideView, CancelRideView, UpdateLocationAPIView, LiveStatusAPIView,
    ReturnRidePromptView, ReturnRideCreateView, ScheduleReturnRideLaterView, SkipReturnRideView,
    ReturnRideOptionsAPIView, ReturnRideScheduleAPIView, ReturnRideSkipAPIView
)

app_name = 'rides'

urlpatterns = [
    path('', RideSearchView.as_view(), name='list'),
    path('search/', RideSearchView.as_view(), name='search'),
    path('create/', RideCreateView.as_view(), name='create'),
    path('my-rides/', MyRidesView.as_view(), name='my_rides'),

    # Return Ride Endpoints
    path('<int:pk>/return-ride-prompt/', ReturnRidePromptView.as_view(), name='return_ride_prompt'),
    path('<int:pk>/return-ride-create/', ReturnRideCreateView.as_view(), name='return_ride_create'),
    path('<int:pk>/return-ride-schedule/', ScheduleReturnRideLaterView.as_view(), name='return_ride_schedule'),
    path('<int:pk>/return-ride-skip/', SkipReturnRideView.as_view(), name='return_ride_skip'),

    # Return Ride REST APIs
    path('api/<int:pk>/return-ride-options/', ReturnRideOptionsAPIView.as_view(), name='api_return_ride_options'),
    path('api/<int:pk>/return-ride-schedule/', ReturnRideScheduleAPIView.as_view(), name='api_return_ride_schedule'),
    path('api/<int:pk>/return-ride-skip/', ReturnRideSkipAPIView.as_view(), name='api_return_ride_skip'),

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


