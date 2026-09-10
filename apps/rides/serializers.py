from rest_framework import serializers
from .models import Ride
from apps.accounts.serializers import UserSerializer


class RideSerializer(serializers.ModelSerializer):
    driver_detail = UserSerializer(source='driver', read_only=True)

    class Meta:
        model = Ride
        fields = (
            'id', 'driver', 'driver_detail', 'origin', 'destination',
            'pickup_point', 'departure_time', 'available_seats',
            'price_per_seat', 'vehicle_info', 'notes', 'status',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'driver', 'created_at', 'updated_at')
