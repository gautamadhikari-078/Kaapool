from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for Kaapool platform.
    Supports both driver and passenger capabilities on a single account.
    """
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)
    profile_picture = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    
    # Verification readiness flags
    is_phone_verified = models.BooleanField(default=False)
    is_verified_driver = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_full_name() or self.username
