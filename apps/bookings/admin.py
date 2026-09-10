from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'passenger', 'ride', 'seats_booked', 'status', 'total_price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('passenger__username', 'ride__origin', 'ride__destination')
