from django import forms
from django.contrib import messages
from django.contrib.auth.password_validation import (
    password_validators_help_texts,
    validate_password,
)
from django.utils.translation import gettext_lazy as _
from pytz import common_timezones

from eventyay.base.models import User
from eventyay.base.models.auth import StaffSession


class StaffSessionForm(forms.ModelForm):
    class Meta:
        model = StaffSession
        fields = ['comment']


class UserEditForm(forms.ModelForm):
    error_messages = {
        'duplicate_identifier': _(
            'There already is an account associated with this e-mail address. Please choose a different one.'
        ),
        'pw_mismatch': _('Please enter the same password twice'),
    }

    new_pw = forms.CharField(
        max_length=255,
        required=False,
        label=_('New password'),
        widget=forms.PasswordInput(),
    )
    new_pw_repeat = forms.CharField(
        max_length=255,
        required=False,
        label=_('Repeat new password'),
        widget=forms.PasswordInput(),
    )
    timezone = forms.ChoiceField(
        choices=((a, a) for a in common_timezones),
        label=_('Default timezone'),
        help_text=_(
            'Only used for views that are not bound to an event. For all '
            'event views, the event timezone is used instead.'
        ),
    )

    class Meta:
        model = User
        fields = [
            'fullname',
            'locale',
            'timezone',
            'email',
            'require_2fa',
            'is_active',
            'is_staff',
            'last_login',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only require email for new users or users that already have an email
        # Allow existing users without email to remain without email
        if self.instance and self.instance.pk and not self.instance.email:
            self.fields['email'].required = False
        else:
            self.fields['email'].required = True
        # Normalize None to empty string to prevent "None" from displaying in form fields
        if self.instance and self.instance.email is None:
            self.initial['email'] = ''
        self.fields['last_login'].disabled = True
        if self.instance and self.instance.auth_backend != 'native':
            del self.fields['new_pw']
            del self.fields['new_pw_repeat']
            self.fields['email'].disabled = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Normalize empty string to None for consistency
        if email == '':
            email = None
        # Allow None/empty email only for existing users who currently have no email
        if not email:
            if self.instance and self.instance.pk and not self.instance.email:
                return None
            # Should not occur: new users have required email; existing users with email keep it
            return email
        # Check for duplicate emails only when an email is provided
        qs = User.objects.filter(email__iexact=email)
        if self.instance is not None and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                self.error_messages['duplicate_identifier'],
                code='duplicate_identifier',
            )
        return email

    def clean_new_pw(self):
        password1 = self.cleaned_data.get('new_pw', '')
        if password1 and validate_password(password1, user=self.instance) is not None:
            raise forms.ValidationError(_(password_validators_help_texts()), code='pw_invalid')
        return password1

    def clean_new_pw_repeat(self):
        password1 = self.cleaned_data.get('new_pw')
        password2 = self.cleaned_data.get('new_pw_repeat')
        if password1 and password1 != password2:
            raise forms.ValidationError(self.error_messages['pw_mismatch'], code='pw_mismatch')

    def clean(self):
        password1 = self.cleaned_data.get('new_pw')

        if password1:
            self.instance.set_password(password1)

        return self.cleaned_data

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved. See below for details.'))
        return super().form_invalid(form)
