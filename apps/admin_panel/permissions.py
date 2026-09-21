from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from apps.admin_panel.models import AuditLog


class AdminRequiredMixin(AccessMixin):
    """
    Mixin that verifies current user is logged in AND has an admin role or staff status.
    Redirects unauthenticated users to /admin/login/.
    Redirects authenticated non-admin users to /admin/login/ with an informative message.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Please log in to access the Admin Panel.")
            return redirect('admin_panel:login')
        
        if getattr(request.user, 'is_blocked', False):
            messages.error(request, "Your account has been blocked.")
            return redirect('accounts:login')

        if not getattr(request.user, 'is_admin', False):
            messages.error(request, f"Access denied. Account '{request.user.email or request.user.username}' does not have administrator privileges. Please log in with an Admin account.")
            return redirect('admin_panel:login')

        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredMixin(AdminRequiredMixin):
    """
    Mixin that checks for a specific granular admin permission code (e.g. 'users.block', 'content.edit').
    """
    required_permission = None

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if isinstance(response, HttpResponseRedirect) or getattr(response, 'status_code', 200) in [301, 302]:
            return response
        if self.required_permission and hasattr(request.user, 'has_admin_permission'):
            if not request.user.has_admin_permission(self.required_permission):
                messages.error(request, f"Permission denied for '{self.required_permission}'.")
                return redirect('admin_panel:dashboard')
        return response


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
