from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'govt_id_type', 'document_status', 'is_verified_driver', 'is_staff')
    list_filter = ('document_status', 'is_verified_driver', 'is_phone_verified', 'is_staff', 'is_superuser')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Kaapool Profile Details', {
            'fields': ('phone_number', 'bio', 'profile_picture', 'is_phone_verified', 'is_verified_driver')
        }),
        ('Identity Documents & Verification', {
            'fields': ('govt_id_type', 'govt_id_number', 'govt_id_front', 'govt_id_back', 'document_status')
        }),
    )
