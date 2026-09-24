import logging
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from apps.rides.models import Ride, ReturnRideReminder
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def validate_return_ride_timing(original_ride, departure_datetime):
    """
    Validates that the return ride departure time is logically after the original ride.
    """
    if not departure_datetime:
        raise ValidationError("Departure date and time are required for the return ride.")

    if departure_datetime <= original_ride.departure_datetime:
        formatted_orig_time = original_ride.departure_datetime.strftime('%d %b %Y, %I:%M %p')
        raise ValidationError(
            f"The return ride cannot be scheduled before or at the same time as the original ride ({formatted_orig_time})."
        )


def trigger_return_ride_reminder_if_needed(ride):
    """
    Trigger in-app notification & update reminder status when original ride completes.
    Only triggers if:
    - Ride is not itself a return ride
    - Ride status is 'completed'
    - Ride has not already created a return ride
    - Reminder is pending or return_ride_status is 'SCHEDULED_FOR_LATER'
    """
    if not ride or ride.is_return_ride:
        return False

    if ride.status != 'completed':
        return False

    # Check duplicate return ride
    if ride.has_return_ride:
        # Mark reminder created if already existing
        ride.reminders.filter(status__in=['PENDING', 'TRIGGERED']).update(status='CREATED')
        if ride.return_ride_status != 'CREATED':
            ride.return_ride_status = 'CREATED'
            ride.save(update_fields=['return_ride_status'])
        return False

    # Check if user scheduled for later
    reminder = ride.reminders.filter(status='PENDING').first()
    is_scheduled_later = (ride.return_ride_status == 'SCHEDULED_FOR_LATER')

    if not reminder and not is_scheduled_later:
        return False

    # Update or create the reminder to TRIGGERED
    now = timezone.now()
    if reminder:
        reminder.status = 'TRIGGERED'
        reminder.triggered_at = now
        reminder.save(update_fields=['status', 'triggered_at'])
    else:
        reminder = ReturnRideReminder.objects.create(
            user=ride.driver,
            original_ride=ride,
            status='TRIGGERED',
            triggered_at=now
        )

    ride.return_ride_status = 'PENDING_CREATION'
    ride.save(update_fields=['return_ride_status'])

    # Send In-App Notification
    try:
        offer_url = reverse('rides:return_ride_offer', kwargs={'pk': ride.id})
        Notification.objects.create(
            user=ride.driver,
            notification_type='return_ride_reminder',
            title='Need a return ride?',
            message=f"Your ride from {ride.origin} to {ride.destination} is completed. Would you like to create a return ride?",
            link=offer_url
        )
        logger.info(f"Triggered return ride reminder notification for Ride #{ride.id} to {ride.driver.username}")
        return True
    except Exception as e:
        logger.error(f"Failed to create return ride notification for Ride #{ride.id}: {e}")
        return False


def handle_ride_cancelled(ride):
    """
    Safely handle cancellation of an original ride:
    Cancels pending reminders and updates return_ride_status so reminders are not triggered.
    """
    if not ride:
        return

    # Cancel pending reminders
    ride.reminders.filter(status='PENDING').update(status='CANCELLED')

    if ride.return_ride_status == 'SCHEDULED_FOR_LATER':
        ride.return_ride_status = 'CANCELLED'
        ride.save(update_fields=['return_ride_status'])


def schedule_return_ride_later(original_ride, user):
    """
    Records that user chose 'Schedule for Later'.
    """
    if original_ride.driver != user and not user.is_staff:
        raise ValidationError("You are not authorized to schedule a return ride for this trip.")

    if original_ride.has_return_ride:
        raise ValidationError("A return ride has already been created for this trip.")

    original_ride.return_ride_status = 'SCHEDULED_FOR_LATER'
    original_ride.save(update_fields=['return_ride_status'])

    reminder, _ = ReturnRideReminder.objects.update_or_create(
        original_ride=original_ride,
        user=original_ride.driver,
        defaults={'status': 'PENDING'}
    )
    return reminder


def skip_return_ride(original_ride, user):
    """
    Records that user skipped return ride creation.
    """
    if original_ride.driver != user and not user.is_staff:
        raise ValidationError("You are not authorized to skip return ride for this trip.")

    original_ride.return_ride_status = 'SKIPPED'
    original_ride.save(update_fields=['return_ride_status'])

    # Dismiss any active reminders
    original_ride.reminders.filter(status__in=['PENDING', 'TRIGGERED', 'OPENED']).update(
        status='SKIPPED',
        dismissed_at=timezone.now()
    )


def create_return_ride(original_ride, user, ride_data):
    """
    Creates a return ride linked to the original ride with authoritative backend validation.
    """
    if original_ride.driver != user and not user.is_staff:
        raise ValidationError("You are not authorized to create a return ride for this trip.")

    if original_ride.is_return_ride:
        raise ValidationError("Cannot create a return ride for a ride that is already a return ride.")

    # Duplicate prevention check
    if original_ride.has_return_ride:
        raise ValidationError("A return ride already exists for this trip.")

    departure_datetime = ride_data.get('departure_datetime')
    validate_return_ride_timing(original_ride, departure_datetime)

    # Set up return ride attributes
    ride_data['driver'] = original_ride.driver
    ride_data['original_ride'] = original_ride
    ride_data['is_return_ride'] = True
    ride_data['status'] = 'scheduled'
    ride_data['return_ride_status'] = 'NOT_REQUESTED'

    return_ride = Ride.objects.create(**ride_data)

    # Update original ride & reminders
    original_ride.return_ride_status = 'CREATED'
    original_ride.save(update_fields=['return_ride_status'])

    original_ride.reminders.filter(status__in=['PENDING', 'TRIGGERED', 'OPENED']).update(
        status='CREATED'
    )

    return return_ride
