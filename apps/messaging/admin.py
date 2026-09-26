from django.contrib import admin
from .models import Conversation, ConversationParticipant, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride', 'booking', 'status', 'last_message_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'ride__origin', 'ride__destination', 'booking__id')


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'unread_count', 'joined_at', 'last_read_at')
    list_filter = ('joined_at',)
    search_fields = ('user__username', 'user__email', 'conversation__id')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__username', 'sender__email', 'message_text', 'conversation__id')
