from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from apps.admin_panel.models import AuditLog


class AdminRequiredMixin(AccessMixin):
    """
    Mixin that allows direct open access to the Admin Panel without sign-in prompt.
    """
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredMixin(AdminRequiredMixin):
    """
    Mixin that allows direct open access to the Admin Panel.
    """
    required_permission = None

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


def log_audit_action(admin_user, action, target_type='', target_id='', details=None, request=None):
    """Helper function to record an audit log entry."""
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

    AuditLog.objects.create(
        admin=admin_user if getattr(admin_user, 'is_authenticated', False) else None,
        action=action,
        target_type=str(target_type),
        target_id=str(target_id),
        details=details or {},
        ip_address=ip_address
    )
