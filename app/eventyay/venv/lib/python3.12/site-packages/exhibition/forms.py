from django import forms
from django.utils.translation import gettext_lazy as _
from eventyay.base.forms import I18nModelForm

from .models import ExhibitorInfo


class ExhibitorInfoForm(I18nModelForm):
    allow_voucher_access = forms.BooleanField(
        required=False,
        label=_('Allowed to access voucher data'),
    )
    allow_lead_access = forms.BooleanField(
        required=False,
        label=_('Allowed to access scanned lead data'),
    )
    lead_scanning_scope_by_device = forms.TypedChoiceField(
        label=_('Lead scanning behavior'),
        choices=(
            (
                False,
                _(
                    'Every attendee is one lead, even when scanned from multiple devices. '
                    'Notes and ratings are shared between devices.'
                ),
            ),
            (
                True,
                _(
                    'Every attendee is a new lead when scanned from a new device. '
                    'Notes and ratings are specific to the device.'
                ),
            ),
        ),
        coerce=lambda value: str(value) == 'True',
        initial=False,
        required=False,
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6}),
        required=False,
        label=_('Comment'),
        help_text=_(
            'The text entered in this field will not be visible to the user and is available for your convenience.'
        ),
    )
    booth_id = forms.CharField(
        required=False,
        label=_('Booth ID'),
    )

    class Meta:
        model = ExhibitorInfo
        localized_fields = '__all__'
        fields = [
            'name',
            'description',
            'url',
            'email',
            'logo',
            'booth_id',
            'booth_name',
            'lead_scanning_enabled',
            'allow_voucher_access',
            'allow_lead_access',
            'lead_scanning_scope_by_device',
        ]
        labels = {
            'name': _('Exhibitor name'),
            'description': _('Exhibitor description'),
            'email': _('Contact email'),
            'logo': _('Exhibitor logo'),
            'url': _('Exhibitor URL'),
            'booth_name': _('Booth name'),
            'lead_scanning_enabled': _('Allow lead scanning'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['lead_scanning_scope_by_device'] = self.instance.lead_scanning_scope_by_device
        description_field = self.fields.get('description')
        if description_field:
            widget = description_field.widget
            if isinstance(widget, forms.MultiWidget):
                for sub_widget in widget.widgets:
                    sub_widget.attrs.setdefault('rows', 4)
            else:
                widget.attrs.setdefault('rows', 4)
