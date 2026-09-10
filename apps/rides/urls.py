from django.urls import path
from .views import RideSearchView, RideCreateView, RideDetailView, MyRidesView

app_name = 'rides'

urlpatterns = [
    path('', RideSearchView.as_view(), name='list'),
    path('search/', RideSearchView.as_view(), name='search'),
    path('create/', RideCreateView.as_view(), name='create'),
    path('my-rides/', MyRidesView.as_view(), name='my_rides'),
    path('<int:pk>/', RideDetailView.as_view(), name='detail'),
]
