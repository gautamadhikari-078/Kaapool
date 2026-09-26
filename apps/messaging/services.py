import html
import logging
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.messaging.models import Conversation, ConversationParticipant, Message
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def get_or_create_conversation_for_booking(booking):
    """
    Creates or retrieves the private conversation for a given confirmed/valid booking.
    Ensures idempotency and adds both ride creator (host) and booker (passenger) as participants.
    """
    if not booking or not booking.ride:
        raise ValidationError("Invalid booking or missing ride reference.")

    with transaction.atomic():
        conversation, created = Conversation.objects.select_for_update().get_or_create(
            booking=booking,
            defaults={
                'ride': booking.ride,
                'status': 'read_only' if booking.status == 'cancelled' else 'active',
                'last_message_at': timezone.now()
            }
        )

        if not created and booking.status == 'cancelled' and conversation.status == 'active':
            conversation.status = 'read_only'
            conversation.save(update_fields=['status', 'updated_at'])

        # Ensure Driver/Host is participant
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            user=booking.ride.driver
        )

        # Ensure Passenger is participant
        ConversationParticipant.objects.get_or_create(
            conversation=conversation,
            user=booking.passenger
        )

        return conversation


def send_message_service(conversation, sender, message_text):
    """
    Validates, sanitizes, and stores a text message in the database.
    Updates conversation metadata, unread counts, broadcasts WebSocket event, and handles offline notifications.
    """
    if not sender or not sender.is_authenticated:
        raise PermissionDenied("User must be authenticated to send messages.")

    if not conversation:
        raise ValidationError("Conversation does not exist.")

    # Verify participation
    participant = ConversationParticipant.objects.filter(conversation=conversation, user=sender).first()
    if not participant:
        raise PermissionDenied("You are not a participant in this conversation.")

    # Check conversation lifecycle / booking state
    if conversation.status in ['closed', 'read_only', 'archived'] or conversation.booking.status == 'cancelled':
        raise ValidationError("Sending new messages is disabled because this booking/conversation is cancelled or closed.")

    # Validate message length & content
    raw_text = str(message_text or '').strip()
    if not raw_text:
        raise ValidationError("Message text cannot be empty.")
    if len(raw_text) > 2000:
        raise ValidationError("Message text exceeds maximum allowed length of 2000 characters.")

    # Sanitize message text to prevent XSS
    sanitized_text = html.escape(raw_text)

    now = timezone.now()

    with transaction.atomic():
        msg_obj = Message.objects.create(
            conversation=conversation,
            sender=sender,
            message_text=sanitized_text,
            created_at=now,
            status='sent'
        )

        conversation.last_message_at = msg_obj.created_at
        conversation.save(update_fields=['last_message_at', 'updated_at'])

        # Increment unread count for other participants
        other_participants = ConversationParticipant.objects.filter(
            conversation=conversation
        ).exclude(user=sender)

        for p in other_participants:
            p.unread_count += 1
            p.save(update_fields=['unread_count'])

            # Trigger in-app notification & email for offline users
            _notify_recipient(p.user, sender, conversation, sanitized_text)

    # Broadcast real-time message via Django Channels
    _broadcast_websocket_message(conversation.id, msg_obj)

    return msg_obj


def mark_conversation_as_read(conversation, user):
    """
    Marks all messages in the conversation as read for the specified participant user.
    Resets unread count to 0.
    """
    if not user or not user.is_authenticated:
        return

    participant = ConversationParticipant.objects.filter(conversation=conversation, user=user).first()
    if not participant:
        return

    now = timezone.now()

    with transaction.atomic():
        participant.unread_count = 0
        participant.last_read_at = now
        participant.save(update_fields=['unread_count', 'last_read_at'])

        Message.objects.filter(
            conversation=conversation
        ).exclude(sender=user).filter(read_at__isnull=True).update(read_at=now, status='read')


def _broadcast_websocket_message(conversation_id, message_obj):
    """Helper to broadcast message event to Channels group chat_<conversation_id>."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{conversation_id}",
                {
                    "type": "chat_message",
                    "id": message_obj.id,
                    "conversation_id": conversation_id,
                    "sender_id": message_obj.sender_id,
                    "sender_name": message_obj.sender.get_full_name() or message_obj.sender.username,
                    "message_text": message_obj.message_text,
                    "created_at": message_obj.created_at.isoformat(),
                    "status": message_obj.status,
                }
            )
    except Exception as e:
        logger.error(f"Failed to broadcast WebSocket chat message: {e}")


def _notify_recipient(recipient, sender, conversation, message_snippet):
    """Creates in-app notification & triggers email notification if recipient is inactive."""
    try:
        sender_name = sender.get_full_name() or sender.username
        # In-app notification
        Notification.objects.create(
            user=recipient,
            title=f"New message from {sender_name}",
            message=f"{sender_name}: {message_snippet[:80]}...",
            notification_type="new_message",
            link=f"/messaging/chat/{conversation.id}/"
        )
    except Exception as e:
        logger.error(f"Failed to create message in-app notification: {e}")

    try:
        # Check if recipient is inactive (> 5 minutes ago)
        from django.utils import timezone
        import datetime
        now = timezone.now()
        is_inactive = False
        if not getattr(recipient, 'last_activity_at', None):
            is_inactive = True
        elif (now - recipient.last_activity_at) > datetime.timedelta(minutes=5):
            is_inactive = True

        if is_inactive:
            from apps.core.email_service import EmailService
            EmailService.send_inbox_message_notification(recipient, sender_name)
    except Exception as e:
        logger.error(f"Failed to send email message notification: {e}")
