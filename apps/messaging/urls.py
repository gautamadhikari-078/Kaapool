from django.urls import path
from .views import InboxView, AddPhotoInfoView, StayUpdatedInfoView, ChatDetailView

app_name = 'messaging'

urlpatterns = [
    path('', InboxView.as_view(), name='inbox'),
    path('add-photo/', AddPhotoInfoView.as_view(), name='add_photo_info'),
    path('stay-updated/', StayUpdatedInfoView.as_view(), name='stay_updated_info'),
    path('chat/<int:user_id>/', ChatDetailView.as_view(), name='chat_detail'),
]
