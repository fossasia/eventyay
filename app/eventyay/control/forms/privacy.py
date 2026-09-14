from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.privacy import ThirdPartyService


class ThirdPartyServiceForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyService
        fields = [
            'title',
            'name',
            'provider',
            'purpose',
            'category',
            'enabled',
            'privacy_policy_url',
            'cookie_names',
            'data_processed',
            'region',
            'dpa_status',
        ]
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3}),
            'cookie_names': forms.Textarea(attrs={'rows': 3}),
            'data_processed': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model allows a blank category, but a service without one is left
        # out of the consent banner entirely, so it would never be blocked.
        # Only enforced for new services, so an older service without a
        # category can still be opened and classified.
        self.fields['category'].required = not self.instance.pk
        self.fields['category'].choices = [('', _('Choose a consent category'))] + [
            choice for choice in self.fields['category'].choices if choice[0]
        ]
        if self.instance.pk:
            # Blocked scripts are matched on this identifier, so renaming a live
            # service would silently stop blocking them.
            self.fields['name'].disabled = True
            self.fields['name'].help_text = _('The identifier cannot be changed once the service exists.')
