from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError

from apps.messaging.models import Conversation, ConversationParticipant, Message
from apps.messaging.api_views import APIMessageViewSet  # noqa
from apps.messaging.services import (
    get_or_create_conversation_for_booking,
    send_message_service,
    mark_conversation_as_read
)

User = get_user_model()


class InboxView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'messaging/inbox.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        user = self.request.user
        conversation_ids = ConversationParticipant.objects.filter(
            user=user
        ).values_list('conversation_id', flat=True)

        return Conversation.objects.filter(
            id__in=conversation_ids
        ).select_related('ride', 'booking', 'booking__passenger', 'ride__driver').prefetch_related('participants', 'messages').order_by('-last_message_at', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        conversations_data = []

        for conv in context['conversations']:
            other_part = conv.participants.exclude(user=user).select_related('user').first()
            other_user = other_part.user if other_part else None
            my_part = conv.participants.filter(user=user).first()
            unread_count = my_part.unread_count if my_part else 0
            last_msg = conv.messages.order_by('-created_at').first()

            conversations_data.append({
                'conversation': conv,
                'other_user': other_user,
                'ride': conv.ride,
                'booking': conv.booking,
                'unread_count': unread_count,
                'last_message': last_msg,
            })

        context['inbox_items'] = conversations_data
        return context


class ChatDetailView(LoginRequiredMixin, View):
    def get(self, request, conversation_id=None, user_id=None, *args, **kwargs):
        user = request.user
        conversation = None

        if conversation_id:
            conversation = get_object_or_404(Conversation, id=conversation_id)
        elif user_id:
            # Fallback for legacy URL structure: find conversation between request.user & user_id
            other_user = get_object_or_404(User, id=user_id)
            conversation = Conversation.objects.filter(
                participants__user=user
            ).filter(
                participants__user=other_user
            ).distinct().first()

            if not conversation:
                messages.error(request, "No active ride booking conversation found with this user.")
                return redirect('messaging:inbox')

        # Verify participation
        if not ConversationParticipant.objects.filter(conversation=conversation, user=user).exists():
            raise PermissionDenied("You are not a participant in this conversation.")

        # Mark conversation read for current user
        mark_conversation_as_read(conversation, user)

        other_part = conversation.participants.exclude(user=user).select_related('user').first()
        other_user = other_part.user if other_part else None

        chat_messages = Message.objects.filter(
            conversation=conversation
        ).select_related('sender').order_by('created_at')

        context = {
            'conversation': conversation,
            'other_user': other_user,
            'ride': conversation.ride,
            'booking': conversation.booking,
            'chat_messages': chat_messages,
            'is_disabled': conversation.status in ['closed', 'read_only', 'archived'] or conversation.booking.status == 'cancelled'
        }
        return render(request, 'messaging/chat_detail.html', context)

    def post(self, request, conversation_id=None, user_id=None, *args, **kwargs):
        user = request.user
        conversation = None

        if conversation_id:
            conversation = get_object_or_404(Conversation, id=conversation_id)
        elif user_id:
            other_user = get_object_or_404(User, id=user_id)
            conversation = Conversation.objects.filter(
                participants__user=user
            ).filter(
                participants__user=other_user
            ).distinct().first()

        if not conversation or not ConversationParticipant.objects.filter(conversation=conversation, user=user).exists():
            raise PermissionDenied("You are not a participant in this conversation.")

        content = request.POST.get('content', '').strip()
        if content:
            try:
                send_message_service(conversation, user, content)
            except (PermissionDenied, ValidationError) as err:
                messages.error(request, str(err))
            except Exception:
                messages.error(request, "Failed to send message.")

        return redirect('messaging:chat_detail', conversation_id=conversation.id)


class AddPhotoInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'messaging/add_photo_info.html'


class StayUpdatedInfoView(LoginRequiredMixin, TemplateView):
    template_name = 'messaging/stay_updated_info.html'
