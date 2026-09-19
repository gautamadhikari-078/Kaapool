from django.contrib import admin
from .models import Ride


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ('origin', 'destination', 'driver', 'departure_datetime', 'available_seats', 'price_per_seat', 'status')
    list_filter = ('status', 'departure_datetime')
    search_fields = ('origin', 'destination', 'driver__username', 'driver__email')
