from __future__ import annotations

from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm
from eventyay.base.models import Product

from .settings import FEE_MODE_CHOICES, MAX_PRICE_CHOICES


class ResaleSettingsForm(SettingsForm):
    resale_enabled = forms.BooleanField(
        label=_('Enable ticket resale marketplace'),
        required=False,
        help_text=_('When enabled, attendees can list eligible tickets and buyers can purchase them.'),
    )
    resale_suspended = forms.BooleanField(
        label=_('Suspend marketplace'),
        required=False,
        help_text=_('Temporarily close buying and selling without clearing configuration.'),
    )
    resale_products = forms.ModelMultipleChoiceField(
        label=_('Eligible ticket types'),
        required=False,
        queryset=Product.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text=_('Leave empty to allow all ticket types.'),
    )
    resale_fee_mode = forms.ChoiceField(
        label=_('Processing fee type'),
        choices=FEE_MODE_CHOICES,
    )
    resale_fee_fixed = forms.DecimalField(
        label=_('Fixed processing fee'),
        min_value=Decimal('0.00'),
        decimal_places=2,
        max_digits=10,
        required=False,
    )
    resale_fee_percent = forms.DecimalField(
        label=_('Percentage processing fee'),
        min_value=Decimal('0.00'),
        max_value=Decimal('100.00'),
        decimal_places=2,
        max_digits=5,
        required=False,
    )
    resale_available_from = forms.SplitDateTimeField(
        label=_('Marketplace opens'),
        required=False,
    )
    resale_available_until = forms.SplitDateTimeField(
        label=_('Marketplace closes'),
        required=False,
    )
    resale_max_price_mode = forms.ChoiceField(
        label=_('Maximum resale price'),
        choices=MAX_PRICE_CHOICES,
        help_text=_('By default sellers may not ask more than the original purchase price.'),
    )
    resale_reservation_minutes = forms.IntegerField(
        label=_('Buyer reservation period (minutes)'),
        min_value=1,
        max_value=24 * 60,
        help_text=_('How long a reserved listing stays held during checkout.'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resale_products'].queryset = self.obj.products.filter(active=True).order_by(
            'category__position', 'position', 'name'
        )
        product_ids = self.obj.settings.get('resale_products', as_type=list) or []
        self.initial['resale_products'] = self.fields['resale_products'].queryset.filter(
            pk__in=[int(p) for p in product_ids if str(p).isdigit()]
        )

    def clean(self):
        cleaned = super().clean()
        opens = cleaned.get('resale_available_from')
        closes = cleaned.get('resale_available_until')
        if opens and closes and closes <= opens:
            raise forms.ValidationError(_('The closing date must be after the opening date.'))
        return cleaned

    def save(self):
        products = self.cleaned_data.pop('resale_products', Product.objects.none())
        self.obj.settings.set('resale_products', [str(p.pk) for p in products])
        return super().save()


class ResaleSellForm(forms.Form):
    price = forms.DecimalField(
        label=_('Your asking price'),
        min_value=Decimal('0.01'),
        decimal_places=2,
        max_digits=13,
    )
    confirm = forms.BooleanField(
        label=_('I understand the resale conditions and want to list this ticket.'),
        required=True,
    )

    def __init__(self, *args, max_price=None, **kwargs):
        self.max_price = max_price
        super().__init__(*args, **kwargs)
        if max_price is not None:
            self.fields['price'].max_value = max_price
            self.fields['price'].help_text = _('Maximum: {price}').format(price=max_price)

    def clean_price(self):
        price = self.cleaned_data['price']
        if self.max_price is not None and price > self.max_price:
            raise forms.ValidationError(
                _('The price cannot exceed the original purchase price of {price}.').format(price=self.max_price)
            )
        return price
