from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms.widgets import SplitDateTimePickerWidget
from eventyay.base.models.giftcards import GiftCard
from eventyay.control.forms import SplitDateTimeField


class GiftCardCreateForm(forms.ModelForm):
    value = forms.DecimalField(label=_('Gift card value'), min_value=Decimal('0.00'))

    def __init__(self, *args, **kwargs):
        self.organizer = kwargs.pop('organizer')
        initial = kwargs.pop('initial', {})
        initial['expires'] = self.organizer.default_gift_card_expiry
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def clean_secret(self):
        secret = self.cleaned_data.get('secret')
        if self.organizer.issued_gift_cards.filter(secret__iexact=secret).exists():
            raise ValidationError(_('A gift card with the same secret already exists in your organizer account.'))

        return secret

    class Meta:
        model = GiftCard
        fields = ['secret', 'currency', 'testmode', 'expires', 'conditions']
        field_classes = {'expires': SplitDateTimeField}
        widgets = {
            'expires': SplitDateTimePickerWidget,
            'conditions': forms.Textarea(attrs={'rows': 2}),
        }
