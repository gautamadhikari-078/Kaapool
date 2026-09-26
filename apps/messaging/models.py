from django.db import models
from django.conf import settings
from apps.rides.models import Ride
from apps.bookings.models import Booking


class Conversation(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('read_only', 'Read Only'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    )

    ride = models.ForeignKey(
        Ride,
        on_delete=models.CASCADE,
        related_name='conversations',
        db_index=True
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='conversation',
        db_index=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        return f"Conversation #{self.id} for Booking #{self.booking_id} (Ride #{self.ride_id})"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='participants',
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_participations',
        db_index=True
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_message_id = models.PositiveIntegerField(null=True, blank=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('conversation', 'user')
        indexes = [
            models.Index(fields=['conversation', 'user']),
            models.Index(fields=['user', 'unread_count']),
        ]

    def __str__(self):
        return f"Participant {self.user} in Conversation #{self.conversation_id}"


class Message(models.Model):
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_conversation_messages',
        db_index=True
    )
    message_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]

    def __str__(self):
        return f"Message #{self.id} from {self.sender} in Conversation #{self.conversation_id}"
