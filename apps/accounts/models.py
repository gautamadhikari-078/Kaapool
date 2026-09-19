from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for Kaapool platform.
    Supports both driver and passenger capabilities on a single account.
    """
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)
    profile_picture = models.ImageField(upload_to='profile_photos/', blank=True, null=True)

    # Verification readiness flags & Document Storage
    is_phone_verified = models.BooleanField(default=False)
    is_verified_driver = models.BooleanField(default=False)

    govt_id_type = models.CharField(max_length=50, blank=True, null=True, default='')
    govt_id_number = models.CharField(max_length=50, blank=True, null=True, default='')
    govt_id_front = models.ImageField(upload_to='user_documents/', blank=True, null=True)
    govt_id_back = models.ImageField(upload_to='user_documents/', blank=True, null=True)
    document_status = models.CharField(
        max_length=30,
        choices=(
            ('NOT_UPLOADED', 'Not Uploaded'),
            ('PENDING', 'Pending Verification'),
            ('VERIFIED', 'Verified'),
            ('REJECTED', 'Rejected'),
        ),
        default='NOT_UPLOADED'
    )

    @property
    def has_uploaded_documents(self):
        return bool(self.govt_id_front or self.govt_id_back or self.govt_id_number or self.is_verified_driver or self.document_status in ['PENDING', 'VERIFIED'])

    ROLE_CHOICES = (
        ('user', 'User'),
        ('super_admin', 'Super Admin'),
        ('operations_admin', 'Operations Admin'),
        ('verification_admin', 'Verification Admin'),
        ('support_admin', 'Support Admin'),
        ('content_admin', 'Content Admin'),
        ('finance_admin', 'Finance Admin'),
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='user')
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True, default='')
    custom_permissions = models.JSONField(default=dict, blank=True)

    # Email Verification & Activity Tracking Flags
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    last_activity_at = models.DateTimeField(blank=True, null=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    last_login_ip = models.CharField(max_length=45, blank=True, null=True)
    last_login_user_agent = models.TextField(blank=True, null=True)

    # Marketing & Preference Flags
    marketing_consent = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_admin(self):
        return self.is_superuser or self.is_staff or self.role in [
            'super_admin', 'operations_admin', 'verification_admin',
            'support_admin', 'content_admin', 'finance_admin'
        ]

    def has_admin_permission(self, perm_code):
        if self.is_superuser or self.role == 'super_admin':
            return True
        if not self.is_admin:
            return False

        role_permissions = {
            'operations_admin': ['rides.view', 'rides.manage', 'rides.cancel', 'bookings.view', 'bookings.manage', 'drivers.view', 'drivers.manage', 'vehicles.view', 'vehicles.manage', 'users.view'],
            'verification_admin': ['verification.view', 'verification.review', 'drivers.view', 'drivers.manage', 'vehicles.view', 'vehicles.manage', 'users.view'],
            'support_admin': ['complaints.view', 'complaints.manage', 'users.view', 'users.edit', 'users.block', 'notifications.manage'],
            'content_admin': ['content.view', 'content.create', 'content.edit', 'content.publish', 'faq.manage', 'blogs.manage'],
            'finance_admin': ['payments.view', 'payments.refund', 'bookings.view', 'rides.view'],
        }

        allowed_perms = role_permissions.get(self.role, [])
        if self.custom_permissions and isinstance(self.custom_permissions, dict):
            if perm_code in self.custom_permissions:
                return bool(self.custom_permissions[perm_code])

        return perm_code in allowed_perms

    @property
    def age(self):
        if self.date_of_birth:
            import datetime
            today = datetime.date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

    def __str__(self):
        return self.get_full_name() or self.username


class EmailOTP(models.Model):
    """
    Secure 6-Digit OTP Model for Email Verification & Security.
    Supports expiry, single-use, rate limits, and attempt caps.
    """
    PURPOSE_CHOICES = (
        ('signup', 'Account Verification'),
        ('password_reset', 'Password Reset'),
        ('security', 'Security Verification'),
    )

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='email_otps')
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    otp_hash = models.CharField(max_length=128, blank=True, default='')
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='signup')
    is_used = models.BooleanField(default=False)
    attempts_count = models.IntegerField(default=0)
    resend_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and self.attempts_count < 5 and timezone.now() <= self.expires_at

    def __str__(self):
        return f"OTP {self.otp_code} for {self.email} ({self.purpose})"
