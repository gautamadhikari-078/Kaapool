import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ride
from .services.return_ride_service import trigger_return_ride_reminder_if_needed, handle_ride_cancelled

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ride)
def ride_status_changed(sender, instance, created, **kwargs):
    """
    Listens for Ride lifecycle updates to trigger or cancel Return Ride flows.
    """
    if not created:
        if instance.status == 'completed':
            trigger_return_ride_reminder_if_needed(instance)
        elif instance.status == 'cancelled':
            handle_ride_cancelled(instance)
