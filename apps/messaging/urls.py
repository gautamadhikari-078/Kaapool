from django.urls import path
from .views import InboxView, AddPhotoInfoView, StayUpdatedInfoView, ChatDetailView
from . import api_views

app_name = 'messaging'

urlpatterns = [
    # Web UI Routes
    path('', InboxView.as_view(), name='inbox'),
    path('chat/<int:conversation_id>/', ChatDetailView.as_view(), name='chat_detail_by_id'),
    path('chat/user/<int:user_id>/', ChatDetailView.as_view(), name='chat_detail'),
    path('add-photo/', AddPhotoInfoView.as_view(), name='add_photo_info'),
    path('stay-updated/', StayUpdatedInfoView.as_view(), name='stay_updated_info'),

    # REST API Routes
    path('api/conversations/', api_views.ConversationListCreateAPIView.as_view(), name='api_conversations_list_create'),
    path('api/conversations/<int:conversation_id>/', api_views.ConversationDetailAPIView.as_view(), name='api_conversation_detail'),
    path('api/conversations/<int:conversation_id>/messages/', api_views.ConversationMessagesAPIView.as_view(), name='api_conversation_messages'),
]
