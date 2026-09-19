from django.db import models
from django.conf import settings
from apps.rides.models import Ride
from apps.bookings.models import Booking


class VerificationRecord(models.Model):
    STATUS_CHOICES = (
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('APPROVED', 'Approved'),
        ('DECLINED', 'Declined'),
        ('RESUBMISSION_REQUESTED', 'Resubmission Requested'),
        ('EXPIRED', 'Expired'),
        ('ABANDONED', 'Abandoned'),
    )
    VERIFICATION_TYPES = (
        ('veriff', 'Veriff Identity'),
        ('sumsub', 'Sumsub Identity'),
        ('manual', 'Manual Review'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_records'
    )
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPES, default='veriff')
    session_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_STARTED')
    decision_reason = models.TextField(blank=True, default='')
    decision_payload = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Verification #{self.id} for {self.user} ({self.status})"


class Complaint(models.Model):
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('UNDER_REVIEW', 'Under Review'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
        ('CLOSED', 'Closed'),
    )
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    CATEGORY_CHOICES = (
        ('ride', 'Ride Issue'),
        ('driver', 'Driver Behavior'),
        ('passenger', 'Passenger Issue'),
        ('payment', 'Payment / Refund'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_complaints'
    )
    related_ride = models.ForeignKey(
        Ride,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints'
    )
    related_booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints'
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='OPEN')
    assigned_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints'
    )
    internal_notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Complaint #{self.id}: {self.subject} ({self.status})"


class FAQ(models.Model):
    CATEGORY_CHOICES = (
        ('general', 'General'),
        ('drivers', 'Drivers'),
        ('passengers', 'Passengers'),
        ('payments', 'Payments & Refunds'),
        ('safety', 'Safety & Security'),
    )

    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    display_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question


class Blog(models.Model):
    CATEGORY_CHOICES = (
        ('travel', 'Travel & Rides'),
        ('safety', 'Safety Guidelines'),
        ('tips', 'Tips & Guides'),
        ('company', 'Company News'),
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='travel')
    author_name = models.CharField(max_length=100, default='Kaapool Team')
    cover_image = models.ImageField(upload_to='blog_covers/', blank=True, null=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True, max_length=500)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title


class WebsiteContent(models.Model):
    SECTION_CHOICES = (
        ('homepage', 'Homepage CMS'),
        ('about', 'About Us'),
        ('contact', 'Contact Details'),
        ('safety', 'Safety Guidelines'),
        ('how_it_works', 'How It Works'),
        ('privacy_policy', 'Privacy Policy'),
        ('terms_conditions', 'Terms & Conditions'),
        ('cancellation_policy', 'Cancellation Policy'),
        ('refund_policy', 'Refund Policy'),
    )

    section = models.CharField(max_length=50, choices=SECTION_CHOICES, unique=True)
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)
    meta_data = models.JSONField(default=dict, blank=True, help_text="Structured CMS fields like stats, features, social links")
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return dict(self.SECTION_CHOICES).get(self.section, self.section)


class AuditLog(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_audit_logs'
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.admin} - {self.action}"


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


class ContactInquiry(models.Model):
    """
    Stores all Contact Us form submissions from website visitors/users.
    Validates email syntax, records email validity status, and connects to Super Admin Panel.
    """
    STATUS_CHOICES = (
        ('NEW', 'New Inquiry'),
        ('RESPONDED', 'Responded'),
        ('INVALID_EMAIL', 'Invalid Email'),
        ('CLOSED', 'Closed'),
    )

    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default='')
    category = models.CharField(max_length=50, default='other')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_email_valid = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NEW')
    
    admin_notes = models.TextField(blank=True, default='')
    admin_replied_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Contact Inquiry from {self.name} ({self.email}) [{self.status}]"

