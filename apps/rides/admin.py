from django.contrib import admin
from .models import Ride, ReturnRideReminder, Vehicle


class BookingInline(admin.TabularInline):
    """Inline view of bookings on the Ride admin page."""
    from apps.bookings.models import Booking
    model = Booking
    extra = 0
    readonly_fields = ('passenger', 'seats_booked', 'total_price', 'status', 'created_at')
    can_delete = False
    show_change_link = True


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'origin', 'destination', 'driver',
        'departure_datetime', 'available_seats',
        'price_per_seat', 'status', 'is_return_ride', 'created_at'
    )
    list_filter = ('status', 'is_return_ride', 'departure_datetime', 'created_at')
    search_fields = ('origin', 'destination', 'driver__username', 'driver__email', 'pickup_address', 'drop_address')
    list_editable = ('status',)
    list_per_page = 25
    date_hierarchy = 'departure_datetime'
    readonly_fields = ('created_at', 'updated_at', 'started_at', 'completed_at', 'last_location_update')
    raw_id_fields = ('driver', 'original_ride')
    inlines = [BookingInline]

    fieldsets = (
        ('Route Information', {
            'fields': ('driver', 'origin', 'destination', 'pickup_point')
        }),
        ('Pickup Details', {
            'fields': ('pickup_address', 'pickup_latitude', 'pickup_longitude', 'pickup_place_id'),
            'classes': ('collapse',),
        }),
        ('Drop Details', {
            'fields': ('drop_address', 'drop_latitude', 'drop_longitude', 'drop_place_id'),
            'classes': ('collapse',),
        }),
        ('Route & Distance', {
            'fields': ('route_geometry', 'estimated_distance_km', 'estimated_duration_mins'),
            'classes': ('collapse',),
        }),
        ('Trip Details', {
            'fields': ('departure_datetime', 'available_seats', 'price_per_seat', 'vehicle_info', 'notes', 'status')
        }),
        ('Return Ride', {
            'fields': ('original_ride', 'is_return_ride', 'return_ride_status'),
            'classes': ('collapse',),
        }),
        ('Tracking & Timestamps', {
            'fields': ('started_at', 'completed_at', 'current_driver_lat', 'current_driver_lng', 'last_location_update'),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    actions = ['mark_as_active', 'mark_as_completed', 'mark_as_cancelled']

    @admin.action(description='Mark selected rides as Active')
    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} ride(s) marked as active.')

    @admin.action(description='Mark selected rides as Completed')
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} ride(s) marked as completed.')

    @admin.action(description='Mark selected rides as Cancelled')
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} ride(s) marked as cancelled.')


@admin.register(ReturnRideReminder)
class ReturnRideReminderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'original_ride', 'status', 'created_at', 'triggered_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'original_ride')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'make_model', 'license_plate', 'color', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'make_model', 'license_plate')
    raw_id_fields = ('user',)
