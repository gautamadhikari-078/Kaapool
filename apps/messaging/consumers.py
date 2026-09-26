import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from apps.messaging.models import Conversation, ConversationParticipant
from apps.messaging.services import send_message_service, mark_conversation_as_read

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")
        self.room_group_name = f"chat_{self.conversation_id}"

        # 1. Reject unauthenticated users
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # 2. Reject unauthorized room access (User MUST be a participant)
        is_participant = await self.check_participant_access(self.conversation_id, self.user)
        if not is_participant:
            await self.close(code=4003)
            return

        # 3. Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # 4. Mark conversation as read on connect
        await self.mark_read_async(self.conversation_id, self.user)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get("action", "send_message")
            message_text = data.get("message", "").strip()

            if action == "send_message" and message_text:
                await self.save_and_broadcast_message(self.conversation_id, self.user, message_text)
            elif action == "mark_read":
                await self.mark_read_async(self.conversation_id, self.user)

        except Exception as e:
            await self.send(text_data=json.dumps({
                "error": str(e)
            }))

    async def chat_message(self, event):
        """Handler for event broadcast from group_send."""
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "id": event["id"],
            "conversation_id": event["conversation_id"],
            "sender_id": event["sender_id"],
            "sender_name": event["sender_name"],
            "message_text": event["message_text"],
            "created_at": event["created_at"],
            "status": event["status"],
        }))

    @database_sync_to_async
    def check_participant_access(self, conversation_id, user):
        return ConversationParticipant.objects.filter(
            conversation_id=conversation_id,
            user=user
        ).exists()

    @database_sync_to_async
    def save_and_broadcast_message(self, conversation_id, user, message_text):
        conversation = Conversation.objects.filter(id=conversation_id).first()
        if conversation:
            send_message_service(conversation, user, message_text)

    @database_sync_to_async
    def mark_read_async(self, conversation_id, user):
        conversation = Conversation.objects.filter(id=conversation_id).first()
        if conversation:
            mark_conversation_as_read(conversation, user)
