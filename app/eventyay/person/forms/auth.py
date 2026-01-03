from django import forms
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.common.forms.fields import NewPasswordConfirmationField, NewPasswordField
from eventyay.common.text.phrases import phrases
from eventyay.base.models import User

EMAIL_ADDRESS_ERROR = _('Please choose a different email address.')


class LoginInfoForm(forms.ModelForm):
    error_messages = {'pw_current_wrong': _('The current password you entered was not correct.')}

    old_password = forms.CharField(widget=forms.PasswordInput, label=_('Password (current)'), required=False)
    password = NewPasswordField(label=phrases.base.new_password, required=False)
    password_repeat = NewPasswordConfirmationField(
        label=phrases.base.password_repeat, required=False, confirm_with='password'
    )

    def clean_old_password(self):
        old_pw = self.cleaned_data.get('old_password')
        # SSO-only accounts don't have a usable password, so we skip validation for them
        if self.is_sso_only_account:
            return old_pw
        # For accounts with a local password, validate the current password
        if old_pw and not check_password(old_pw, self.user.password):
            raise forms.ValidationError(self.error_messages['pw_current_wrong'], code='pw_current_wrong')
        return old_pw

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email):
            raise ValidationError(EMAIL_ADDRESS_ERROR)
        return email

    def clean(self):
        data = super().clean()
        password = self.cleaned_data.get('password')
        old_password = self.cleaned_data.get('old_password')

        # For users with a local password, require old_password when making changes
        if not self.is_sso_only_account:
            # Check if any changes are being made (email change or new password)
            email_changed = self.cleaned_data.get('email') != self.user.email
            setting_new_password = bool(password)
            
            if (email_changed or setting_new_password) and not old_password:
                self.add_error('old_password', ValidationError(
                    _('Please enter your current password to make changes.'),
                    code='pw_required'
                ))

        if password and password != self.cleaned_data.get('password_repeat'):
            self.add_error('password_repeat', ValidationError(phrases.base.passwords_differ))
        return data

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs['instance'] = user
        super().__init__(*args, **kwargs)
        
        # Determine if this is an SSO-only account (no usable local password)
        self.is_sso_only_account = not user.has_usable_password()
        
        # For SSO-only accounts, hide the old_password field and update help text
        if self.is_sso_only_account:
            self.fields['old_password'].widget = forms.HiddenInput()
            self.fields['old_password'].required = False
            # Update password field help text for SSO users
            self.fields['password'].help_text = _(
                'You can set a local password to enable email/password login in addition to your SSO login.'
            )

    def save(self):
        super().save()
        password = self.cleaned_data.get('password')
        if password:
            self.user.change_password(password)

    class Meta:
        model = User
        fields = ('email',)
