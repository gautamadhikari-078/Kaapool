from django.urls import path
from .views import InboxView

app_name = 'messaging'

urlpatterns = [
    path('', InboxView.as_view(), name='inbox'),
]
