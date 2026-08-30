from django import forms
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import (
    password_validators_help_texts,
    validate_password,
)
from django.utils.translation import gettext_lazy as _
from eventyay.timezones import common_timezones

from eventyay.base.models import User
from eventyay.common.image import validate_image
from eventyay.control.forms import SingleLanguageWidget


class UserSettingsForm(forms.ModelForm):
    error_messages = {
        'pw_current': _('Please enter your current password if you want to change your password.'),
        'pw_current_wrong': _('The current password you entered was not correct.'),
        'pw_mismatch': _('Please enter the same password twice'),
        'rate_limit': _('For security reasons, please wait 5 minutes before you try again.'),
    }

    profile_picture = forms.ImageField(
        required=False,
        label=_('Profile picture'),
        validators=[validate_image],
        widget=forms.FileInput(attrs={'data-eventyay-file-wrapper': 'disabled'}),
        help_text=_('We recommend uploading a square image at least 400px wide.'),
    )
    clear_profile_picture = forms.BooleanField(
        required=False,
        label=_('Remove profile picture'),
    )
    old_pw = forms.CharField(
        max_length=255,
        required=False,
        label=_('Your current password'),
        widget=forms.PasswordInput(),
    )
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
        fields = ['fullname', 'wikimedia_username', 'profile_picture', 'locale', 'timezone', 'email']
        widgets = {'locale': SingleLanguageWidget}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        self.requires_password_reset = kwargs.pop('require_password_reset', False)
        super().__init__(*args, **kwargs)
        # Email addresses are managed via the dedicated email management page (allauth).
        # The account settings page does not submit an email field, so keep it read-only here.
        self.fields['email'].required = False
        self.fields['email'].disabled = True
        self.fields['wikimedia_username'].disabled = True
        if self.user.auth_backend != 'native':
            del self.fields['old_pw']
            del self.fields['new_pw']
            del self.fields['new_pw_repeat']
        elif self.requires_password_reset:
            for field in ('old_pw', 'new_pw', 'new_pw_repeat'):
                self.fields.pop(field, None)

    def clean_old_pw(self):
        old_pw = self.cleaned_data.get('old_pw')

        if old_pw and settings.HAS_REDIS:
            from django_redis import get_redis_connection

            rc = get_redis_connection('redis')
            cnt = rc.incr('pretix_pwchange_%s' % self.user.pk)
            rc.expire('pretix_pwchange_%s' % self.user.pk, 300)
            if cnt > 10:
                raise forms.ValidationError(
                    self.error_messages['rate_limit'],
                    code='rate_limit',
                )

        if old_pw and not check_password(old_pw, self.user.password):
            raise forms.ValidationError(
                self.error_messages['pw_current_wrong'],
                code='pw_current_wrong',
            )

        return old_pw

    def clean_email(self):
        return self.instance.email

    def clean_new_pw(self):
        password1 = self.cleaned_data.get('new_pw', '')
        if password1 and validate_password(password1, user=self.user) is not None:
            raise forms.ValidationError(_(password_validators_help_texts()), code='pw_invalid')
        return password1

    def clean_new_pw_repeat(self):
        password1 = self.cleaned_data.get('new_pw')
        password2 = self.cleaned_data.get('new_pw_repeat')
        if password1 and password1 != password2:
            raise forms.ValidationError(self.error_messages['pw_mismatch'], code='pw_mismatch')

    def clean(self):
        cleaned_data = super().clean()
        has_new_profile_picture_upload = bool(self.files and self.files.get('profile_picture'))
        if cleaned_data.get('clear_profile_picture') and has_new_profile_picture_upload:
            raise forms.ValidationError(
                _('Cannot upload a new profile picture and remove the existing one at the same time.')
            )

        if cleaned_data.get('clear_profile_picture'):
            cleaned_data['profile_picture'] = None

        password1 = cleaned_data.get('new_pw')
        old_pw = cleaned_data.get('old_pw')

        if not self.requires_password_reset and password1 and not old_pw:
            raise forms.ValidationError(self.error_messages['pw_current'], code='pw_current')

        if password1:
            self.instance.set_password(password1)

        return cleaned_data


class User2FADeviceAddForm(forms.Form):
    name = forms.CharField(label=_('Device name'), max_length=64)
    devicetype = forms.ChoiceField(
        label=_('Device type'),
        widget=forms.RadioSelect,
        choices=(
            ('totp', _('Smartphone with the Authenticator application')),
            ('webauthn', _('WebAuthn-compatible hardware token (e.g. Yubikey)')),
        ),
    )
