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

    # Return Ride Integration
    RETURN_RIDE_STATUS_CHOICES = (
        ('NOT_REQUESTED', 'Not Requested'),
        ('SCHEDULED_FOR_LATER', 'Scheduled for Later'),
        ('PENDING_CREATION', 'Pending Creation'),
        ('CREATED', 'Created'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('SKIPPED', 'Skipped'),
    )

    original_ride = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='return_rides',
        db_index=True,
        help_text="The original ride if this is a return ride"
    )
    is_return_ride = models.BooleanField(default=False, db_index=True)
    return_ride_status = models.CharField(
        max_length=30,
        choices=RETURN_RIDE_STATUS_CHOICES,
        default='NOT_REQUESTED',
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_datetime']
        indexes = [
            models.Index(fields=['driver', 'departure_datetime'], name='ride_driver_dep_idx'),
            models.Index(fields=['driver', 'status'], name='ride_driver_status_idx'),
            models.Index(fields=['original_ride', 'is_return_ride'], name='ride_return_rel_idx'),
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

    @property
    def return_ride(self):
        """Returns the linked return ride if one exists."""
        return self.return_rides.exclude(status='cancelled').first() or self.return_rides.first()

    @property
    def has_return_ride(self):
        """True if an active/valid return ride exists for this original ride."""
        return self.return_rides.exclude(status='cancelled').exists()

    @property
    def can_create_return_ride(self):
        """True if this is an original ride eligible for creating a return ride."""
        if self.is_return_ride or self.original_ride_id is not None:
            return False
        if self.status == 'cancelled':
            return False
        return not self.has_return_ride

    def __str__(self):
        return f"{self.origin} to {self.destination} ({self.departure_datetime.strftime('%Y-%m-%d %H:%M')})"


class ReturnRideReminder(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('TRIGGERED', 'Triggered'),
        ('OPENED', 'Opened'),
        ('CREATED', 'Created'),
        ('SKIPPED', 'Skipped'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='return_ride_reminders'
    )
    original_ride = models.ForeignKey(
        'Ride',
        on_delete=models.CASCADE,
        related_name='reminders'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='ret_remind_user_stat_idx'),
            models.Index(fields=['original_ride', 'status'], name='ret_remind_ride_stat_idx'),
        ]

    def __str__(self):
        return f"Return Ride Reminder: Ride #{self.original_ride_id} for {self.user} [{self.status}]"


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


