from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = (
        ('booking_confirmed', 'Booking Confirmed'),
        ('booking_cancelled', 'Booking Cancelled'),
        ('ride_reminder', 'Ride Reminder'),
        ('return_ride_reminder', 'Return Ride Reminder'),
        ('new_message', 'New Message'),
        ('ride_update', 'Ride Update'),
        ('payment_update', 'Payment Update'),
        ('system', 'System Notification'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='system')
    link = models.CharField(max_length=500, blank=True, default='')
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user}: {self.title}"


class NotificationPreference(models.Model):
    """
    Per-user notification category toggles.
    Allows opting out of non-critical marketing & updates.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference'
    )
    email_account_security = models.BooleanField(default=True)  # Mandatory
    email_ride_updates = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_platform_updates = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user}"


class NotificationLog(models.Model):
    """
    Logs every email attempt, delivery status, and provider message ID.
    """
    CATEGORY_CHOICES = (
        ('TRANSACTIONAL', 'Transactional Email'),
        ('MARKETING', 'Marketing / Re-engagement Email'),
    )
    STATUS_CHOICES = (
        ('QUEUED', 'Queued'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('BOUNCED', 'Bounced'),
        ('OPENED', 'Opened'),
        ('CLICKED', 'Clicked'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    email = models.EmailField()
    notification_type = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='TRANSACTIONAL')
    subject = models.CharField(max_length=255)
    provider_name = models.CharField(max_length=50, default='DjangoSMTP')
    provider_message_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    failure_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    opened_at = models.DateTimeField(blank=True, null=True)
    clicked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.notification_type} -> {self.email}"


class EmailTemplate(models.Model):
    """
    Reusable Email HTML/Text Templates configurable by Super Admin.
    """
    CATEGORY_CHOICES = (
        ('TRANSACTIONAL', 'Transactional'),
        ('MARKETING', 'Marketing'),
    )

    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='TRANSACTIONAL')
    subject_template = models.CharField(max_length=255)
    body_html_template = models.TextField()
    body_text_template = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class EmailAutomationRule(models.Model):
    """
    Automation rules for inactive user re-engagement & automatic reminders.
    """
    TRIGGER_CHOICES = (
        ('inactivity_7d', 'Inactive for 7 days'),
        ('inactivity_21d', 'Inactive for 21 days'),
        ('inactivity_30d', 'Inactive for 30+ days'),
        ('welcome_followup', 'Welcome Follow-up'),
    )

    name = models.CharField(max_length=100)
    event_trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    days_inactive = models.IntegerField(default=7)
    require_email_verified = models.BooleanField(default=True)
    require_marketing_consent = models.BooleanField(default=True)
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE, related_name='automation_rules')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Automation Rule: {self.name} ({self.event_trigger})"
