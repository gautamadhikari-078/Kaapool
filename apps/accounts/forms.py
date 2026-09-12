from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address'}))
    first_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))
    phone_number = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'placeholder': 'Phone Number'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'bio', 'profile_picture')
