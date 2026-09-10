from django.shortcuts import render
from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Homepage view."""
    template_name = 'core/home.html'


class AboutView(TemplateView):
    """About Kaapool page view."""
    template_name = 'core/about.html'


class HowItWorksView(TemplateView):
    """How Kaapool works page view."""
    template_name = 'core/how_it_works.html'


class SafetyView(TemplateView):
    """Safety guidelines page view."""
    template_name = 'core/safety.html'


class ContactView(TemplateView):
    """Contact page view."""
    template_name = 'core/contact.html'
