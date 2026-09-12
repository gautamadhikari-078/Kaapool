from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView, LogoutView as DjangoLogoutView
from django.contrib import messages
from django.views.generic import TemplateView, CreateView, UpdateView
from django.urls import reverse_lazy

from .forms import CustomUserCreationForm
from rest_framework import generics, permissions
from .serializers import UserSerializer, RegisterSerializer

User = get_user_model()


# --- Web Views ---

class CustomLoginView(DjangoLoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class CustomLogoutView(DjangoLogoutView):
    next_page = 'core:home'


class SignUpView(CreateView):
    template_name = 'accounts/signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('core:home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"🎉 Welcome to Kaapool, {user.username}! Your account has been created successfully.")
        
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect(self.success_url)



class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'


# --- REST API Views ---

class APIUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class APIRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
