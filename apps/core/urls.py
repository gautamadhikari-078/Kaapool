from django.urls import path
from .views import HomeView, AboutView, HowItWorksView, SafetyView, ContactView

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('about/', AboutView.as_view(), name='about'),
    path('how-it-works/', HowItWorksView.as_view(), name='how_it_works'),
    path('safety/', SafetyView.as_view(), name='safety'),
    path('contact/', ContactView.as_view(), name='contact'),
]
