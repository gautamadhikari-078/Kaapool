from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.messaging.models import Conversation, ConversationParticipant, Message

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'profile_picture_url']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'message_text', 'created_at', 'status', 'read_at']
        read_only_fields = ['id', 'conversation', 'sender', 'created_at', 'status', 'read_at']


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=True, min_length=1, max_length=2000, trim_whitespace=True)


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    ride_info = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'ride_id', 'booking_id', 'status', 'created_at',
            'updated_at', 'last_message_at', 'other_user', 'ride_info',
            'last_message', 'unread_count'
        ]

    def get_other_user(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        participant = obj.participants.exclude(user=request.user).select_related('user').first()
        if participant:
            return UserMinimalSerializer(participant.user, context=self.context).data
        return None

    def get_ride_info(self, obj):
        ride = obj.ride
        if not ride:
            return None
        return {
            'id': ride.id,
            'origin': ride.origin,
            'destination': ride.destination,
            'pickup_address': ride.pickup_address,
            'drop_address': ride.drop_address,
            'departure_datetime': ride.departure_datetime.isoformat() if ride.departure_datetime else None,
            'status': ride.status,
            'booking_status': obj.booking.status if obj.booking else None,
        }

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'id': last_msg.id,
                'sender_id': last_msg.sender_id,
                'message_text': last_msg.message_text,
                'created_at': last_msg.created_at.isoformat(),
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        part = obj.participants.filter(user=request.user).first()
        return part.unread_count if part else 0
