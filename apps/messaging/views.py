from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from rest_framework import viewsets, permissions
from .models import Message
from .serializers import MessageSerializer


# --- Web Views ---

class InboxView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/inbox.html'
    context_object_name = 'messages'

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user))


# --- REST API ViewSets ---

class APIMessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user))

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
