from django import forms
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Product
from eventyay.plugins.badges.models import BadgeLayout, BadgeProduct
from eventyay.plugins.badges.utils import get_badge_customizable_fields


class BadgeLayoutForm(forms.ModelForm):
    class Meta:
        model = BadgeLayout
        fields = ('name',)


class BadgeLayoutSettingsForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        required=False,
        label=_('Products assigned to this layout'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
    )
    allow_customization = forms.BooleanField(
        required=False,
        label=_('Allow badge customization'),
    )
    allow_badge_editing = forms.BooleanField(
        required=False,
        label=_('Allow badge editing'),
        help_text=_(
            'When enabled, check-in staff can edit badge text for the selected fields before printing an updated badge.'
        ),
    )
    ask_user_fields = forms.MultipleChoiceField(
        required=False,
        label=_('Badge fields'),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.layout = kwargs.pop('layout')
        super().__init__(*args, **kwargs)

        self.fields['products'].queryset = self.event.products.order_by('category__position', 'position')
        self.fields['products'].initial = list(self.layout.product_assignments.values_list('product_id', flat=True))
        if self.layout.default:
            self.fields['products'].help_text = _(
                'Products not explicitly assigned to another layout will also use the default layout.'
            )

        self.customizable_fields = get_badge_customizable_fields(self.event, self.layout)
        choices = [(field['key'], field['label']) for field in self.customizable_fields]
        valid_keys = {choice[0] for choice in choices}
        initial_keys = [key for key in self.layout.ask_user_fields_data if key in valid_keys]

        self.fields['allow_customization'].initial = self.layout.allow_customization
        self.fields['allow_badge_editing'].initial = self.layout.allow_badge_editing
        self.fields['ask_user_fields'].choices = choices
        self.fields['ask_user_fields'].initial = initial_keys

        if not choices:
            self.fields['allow_customization'].disabled = True
            self.fields['allow_badge_editing'].disabled = True
            self.fields['allow_customization'].help_text = _(
                'This layout does not currently contain any dynamic text fields that can be customized.'
            )

    def clean(self):
        cleaned_data = super().clean()
        if not self.customizable_fields:
            cleaned_data['allow_customization'] = False
            cleaned_data['allow_badge_editing'] = False
            cleaned_data['ask_user_fields'] = []
            return cleaned_data

        if not cleaned_data.get('allow_customization'):
            cleaned_data['ask_user_fields'] = []
            cleaned_data['allow_badge_editing'] = False

        return cleaned_data

    @transaction.atomic
    def save(self):
        selected_products = self.cleaned_data['products']
        selected_ids = set(selected_products.values_list('pk', flat=True))

        BadgeProduct.objects.filter(layout=self.layout).exclude(product_id__in=selected_ids).delete()
        for product in selected_products:
            BadgeProduct.objects.update_or_create(product=product, defaults={'layout': self.layout})

        self.layout.allow_customization = self.cleaned_data['allow_customization']
        self.layout.allow_badge_editing = self.cleaned_data['allow_badge_editing']
        self.layout.ask_user_fields_data = self.cleaned_data['ask_user_fields']
        self.layout.save(update_fields=['allow_customization', 'allow_badge_editing', 'ask_user_fields'])
        return self.layout


class BadgeOptionsField(forms.MultipleChoiceField):
    widget = forms.CheckboxSelectMultiple
    badge_option = True

    def __init__(self, *args, hidden_initial=None, **kwargs):
        super().__init__(*args, required=False, **kwargs)
        self._choice_order = [str(value) for value, _label in self.choices]
        self.initial = self.get_meta_initial(hidden_initial)

    def get_meta_initial(self, hidden_values):
        if isinstance(hidden_values, str):
            hidden_values = [hidden_values]
        hidden_values = {str(value) for value in (hidden_values or [])}
        return [value for value in self._choice_order if value not in hidden_values]

    def get_display_value(self, hidden_values):
        visible_values = set(self.get_meta_initial(hidden_values))
        visible_labels = [str(label) for value, label in self.choices if str(value) in visible_values]
        if not visible_labels:
            return str(_('No optional badge fields selected'))
        return ', '.join(visible_labels)

    def clean(self, value):
        selected_values = set(super().clean(value))
        return [choice for choice in self._choice_order if choice not in selected_values]
