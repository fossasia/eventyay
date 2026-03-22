from django import forms
from django.utils.translation import gettext_lazy as _


class LoginForm(forms.Form):
    username = forms.CharField(min_length=1, max_length=128, label=_("Login/Email"))
    password = forms.CharField(min_length=1, widget=forms.PasswordInput, label=_("Password"))
