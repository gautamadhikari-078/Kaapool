from rest_framework import serializers
from .models import Booking
from apps.rides.serializers import RideSerializer
from apps.accounts.serializers import UserSerializer


class BookingSerializer(serializers.ModelSerializer):
    passenger_detail = UserSerializer(source='passenger', read_only=True)
    ride_detail = RideSerializer(source='ride', read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'passenger', 'passenger_detail', 'ride', 'ride_detail',
            'seats_booked', 'status', 'total_price', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'passenger', 'created_at', 'updated_at')
