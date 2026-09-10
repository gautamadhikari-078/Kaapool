from rest_framework import serializers
from .models import Message
from apps.accounts.serializers import UserSerializer


class MessageSerializer(serializers.ModelSerializer):
    sender_detail = UserSerializer(source='sender', read_only=True)
    recipient_detail = UserSerializer(source='recipient', read_only=True)

    class Meta:
        model = Message
        fields = (
            'id', 'sender', 'sender_detail', 'recipient', 'recipient_detail',
            'ride', 'content', 'is_read', 'timestamp'
        )
        read_only_fields = ('id', 'sender', 'timestamp')
