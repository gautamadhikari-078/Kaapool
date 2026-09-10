from django.urls import path
from .views import PaymentsHistoryView

app_name = 'payments'

urlpatterns = [
    path('', PaymentsHistoryView.as_view(), name='history'),
]
