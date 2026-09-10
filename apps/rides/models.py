from django.db import models
from django.conf import settings


class Ride(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offered_rides'
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    pickup_point = models.CharField(max_length=255, blank=True)
    departure_time = models.DateTimeField()
    available_seats = models.PositiveIntegerField(default=1)
    price_per_seat = models.DecimalField(max_digits=8, decimal_places=2)
    vehicle_info = models.CharField(max_length=255, blank=True, help_text="Car make, model, license plate")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_time']

    def __str__(self):
        return f"{self.origin} to {self.destination} ({self.departure_time.strftime('%Y-%m-%d %H:%M')})"
