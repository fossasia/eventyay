from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.base.models.devices import Device
from eventyay.control.forms.event import SafeEventMultipleChoiceField


class DeviceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        self.fields['limit_events'].queryset = organizer.events.filter(
            live=True,
            tickets_published=True,
        ).order_by('-has_subevents', '-date_from')
        self.fields['limit_events'].required = True
        self.fields['all_events'].label = _('All events (including newly created and published ones)')
        self.fields['gate'].queryset = organizer.gates.all()

    def clean(self):
        cleaned_data = super().clean()
        all_events = cleaned_data.get('all_events')
        limit_events = cleaned_data.get('limit_events')

        if not limit_events:
            if all_events:
                if 'limit_events' in self._errors:
                    del self._errors['limit_events']
                cleaned_data['limit_events'] = self.fields['limit_events'].queryset.none()
            else:
                if 'limit_events' in self._errors:
                    del self._errors['limit_events']
                self.add_error(
                    'limit_events',
                    _('Your device will not have access to anything, please select some events.')
                )

        return cleaned_data

    class Meta:
        model = Device
        fields = ['name', 'all_events', 'limit_events', 'security_profile', 'gate']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(
                attrs={
                    'data-inverse-dependency': '#id_all_events',
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
        }
        field_classes = {'limit_events': SafeEventMultipleChoiceField}
