import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.bookings.models import Booking
from apps.messaging.services import get_or_create_conversation_for_booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def handle_booking_post_save(sender, instance, created, **kwargs):
    """
    Listens for Booking saved events.
    Automatically provisions or updates the ride-linked conversation when status is confirmed/cancelled.
    """
    try:
        if instance.status in ['confirmed', 'completed', 'cancelled']:
            get_or_create_conversation_for_booking(instance)
    except Exception as e:
        logger.error(f"Error provisioning conversation for Booking #{instance.id}: {e}")
