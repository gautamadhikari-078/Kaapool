from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework import viewsets, permissions
from .models import Notification
from .serializers import NotificationSerializer


# --- Web Views ---

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notifications.html'
    context_object_name = 'notifications'

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_notifs = Notification.objects.filter(user=self.request.user)
        context['unread_count'] = user_notifs.filter(is_read=False).count()
        context['total_count'] = user_notifs.count()
        return context


# --- REST API ViewSets ---

class APINotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
