from django.db import models
from django.conf import settings


class Ride(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
        ('active', 'Active'),
    )

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offered_rides'
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    pickup_point = models.CharField(max_length=255, blank=True)

    # Coordinates & Routing
    pickup_address = models.CharField(max_length=255, blank=True)
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    pickup_place_id = models.CharField(max_length=255, blank=True)

    drop_address = models.CharField(max_length=255, blank=True)
    drop_latitude = models.FloatField(null=True, blank=True)
    drop_longitude = models.FloatField(null=True, blank=True)
    drop_place_id = models.CharField(max_length=255, blank=True)


    route_geometry = models.JSONField(null=True, blank=True, help_text="GeoJSON coordinates array [[lng, lat], ...]")
    estimated_distance_km = models.FloatField(null=True, blank=True)
    estimated_duration_mins = models.IntegerField(null=True, blank=True)

    departure_datetime = models.DateTimeField(db_index=True)
    available_seats = models.PositiveIntegerField(default=1)
    price_per_seat = models.DecimalField(max_digits=8, decimal_places=2)
    vehicle_info = models.CharField(max_length=255, blank=True, help_text="Car make, model, license plate")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Live Tracking & Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    current_driver_lat = models.FloatField(null=True, blank=True)
    current_driver_lng = models.FloatField(null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)
    actual_gps_track = models.JSONField(default=list, blank=True, help_text="Historical driver GPS points [{lat, lng, timestamp}, ...]")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_datetime']
        indexes = [
            models.Index(fields=['driver', 'departure_datetime'], name='ride_driver_dep_idx'),
            models.Index(fields=['driver', 'status'], name='ride_driver_status_idx'),
        ]

    @property
    def departure_time(self):
        return self.departure_datetime

    @departure_time.setter
    def departure_time(self, val):
        self.departure_datetime = val

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status in ['scheduled', 'active'] and self.departure_datetime <= timezone.now()

    def __str__(self):
        return f"{self.origin} to {self.destination} ({self.departure_datetime.strftime('%Y-%m-%d %H:%M')})"


class Vehicle(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    make_model = models.CharField(max_length=255)
    license_plate = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    features = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        if self.license_plate:
            return f"{self.make_model} ({self.license_plate.upper()})"
        return self.make_model

