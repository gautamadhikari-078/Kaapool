from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_verified_driver', 'is_staff')
    list_filter = ('is_verified_driver', 'is_phone_verified', 'is_staff', 'is_superuser')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Kaapool Profile Details', {'fields': ('phone_number', 'bio', 'profile_picture', 'is_phone_verified', 'is_verified_driver')}),
    )
