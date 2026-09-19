from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib import messages

from rest_framework import viewsets, permissions
from .models import Message
from .serializers import MessageSerializer

User = get_user_model()


# --- Web Views ---

class InboxView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'messaging/inbox.html'
    context_object_name = 'inbox_messages'


    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user)).select_related('sender', 'recipient', 'ride').order_by('-timestamp')


class AddPhotoInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'messaging/add_photo_info.html'


class StayUpdatedInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'messaging/stay_updated_info.html'


class ChatDetailView(LoginRequiredMixin, View):
    def get(self, request, user_id, *args, **kwargs):
        other_user = get_object_or_404(User, id=user_id)
        messages_qs = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=other_user)) |
            (Q(sender=other_user) & Q(recipient=request.user))
        ).select_related('sender', 'recipient', 'ride').order_by('timestamp')

        # Mark received messages as read
        Message.objects.filter(sender=other_user, recipient=request.user, is_read=False).update(is_read=True)

        latest_message = messages_qs.last()
        ride = latest_message.ride if latest_message else None

        context = {
            'other_user': other_user,
            'chat_messages': messages_qs,
            'ride': ride,
        }
        return render(request, 'messaging/chat_detail.html', context)

    def post(self, request, user_id, *args, **kwargs):
        other_user = get_object_or_404(User, id=user_id)
        content = request.POST.get('content', '').strip()
        if content:
            latest_message = Message.objects.filter(
                (Q(sender=request.user) & Q(recipient=other_user)) |
                (Q(sender=other_user) & Q(recipient=request.user))
            ).last()
            ride = latest_message.ride if latest_message else None

            msg_obj = Message.objects.create(
                sender=request.user,
                recipient=other_user,
                ride=ride,
                content=content
            )

            # Check if recipient is offline/inactive (>5 minutes ago or null)
            from django.utils import timezone
            import datetime
            now = timezone.now()
            is_inactive = False
            if not getattr(other_user, 'last_activity_at', None):
                is_inactive = True
            elif (now - other_user.last_activity_at) > datetime.timedelta(minutes=5):
                is_inactive = True

            if is_inactive:
                try:
                    from apps.core.email_service import EmailService
                    sender_name = request.user.get_full_name() or request.user.username
                    EmailService.send_inbox_message_notification(other_user, sender_name)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Error triggering inbox message email: {e}")

        return redirect('messaging:chat_detail', user_id=user_id)


# --- REST API ViewSets ---

class APIMessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user))

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
