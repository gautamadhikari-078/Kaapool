from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets
from rest_framework.throttling import UserRateThrottle
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from apps.messaging.models import Conversation, ConversationParticipant, Message
from apps.bookings.models import Booking
from apps.messaging.serializers import (
    ConversationSerializer,
    MessageSerializer,
    SendMessageSerializer
)
from apps.messaging.services import (
    get_or_create_conversation_for_booking,
    send_message_service,
    mark_conversation_as_read
)


class MessageThrottle(UserRateThrottle):
    rate = '30/minute'


class ConversationListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """GET /api/conversations - List all conversations where the authenticated user is a participant."""
        user = request.user
        conversation_ids = ConversationParticipant.objects.filter(
            user=user
        ).values_list('conversation_id', flat=True)

        conversations = Conversation.objects.filter(
            id__in=conversation_ids
        ).select_related('ride', 'booking').prefetch_related('participants', 'messages').order_by('-last_message_at', '-created_at')

        serializer = ConversationSerializer(conversations, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """POST /api/conversations - Provision/retrieve conversation for a confirmed booking."""
        booking_id = request.data.get('booking_id')
        if not booking_id:
            return Response({'error': 'booking_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        booking = get_object_or_404(Booking, id=booking_id)

        # Authorization check: Requester must be driver or passenger
        if request.user != booking.passenger and request.user != booking.ride.driver:
            return Response({'error': 'You are not authorized to access chat for this booking.'}, status=status.HTTP_403_FORBIDDEN)

        if booking.status not in ['confirmed', 'completed', 'cancelled']:
            return Response({'error': 'Chat is only available for confirmed or completed bookings.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conversation = get_or_create_conversation_for_booking(booking)
            serializer = ConversationSerializer(conversation, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ConversationDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conversation_id, *args, **kwargs):
        """GET /api/conversations/{conversation_id} - Fetch details of a specific conversation."""
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Verify participation
        if not ConversationParticipant.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({'error': 'You are not a participant in this conversation.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ConversationSerializer(conversation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationMessagesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [MessageThrottle]

    def get(self, request, conversation_id, *args, **kwargs):
        """GET /api/conversations/{conversation_id}/messages - Get message history."""
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Verify participation
        if not ConversationParticipant.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({'error': 'You are not a participant in this conversation.'}, status=status.HTTP_403_FORBIDDEN)

        # Mark messages as read for this user
        mark_conversation_as_read(conversation, request.user)

        messages = Message.objects.filter(
            conversation=conversation
        ).select_related('sender').order_by('created_at')

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, conversation_id, *args, **kwargs):
        """POST /api/conversations/{conversation_id}/messages - Send a message."""
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Verify participation
        if not ConversationParticipant.objects.filter(conversation=conversation, user=request.user).exists():
            return Response({'error': 'You are not a participant in this conversation.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg_obj = send_message_service(
                conversation=conversation,
                sender=request.user,
                message_text=serializer.validated_data['message']
            )
            return Response(MessageSerializer(msg_obj, context={'request': request}).data, status=status.HTTP_201_CREATED)
        except PermissionDenied as pe:
            return Response({'error': str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as ve:
            return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Failed to process message request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class APIMessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(conversation__participants__user=user)).distinct()

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
