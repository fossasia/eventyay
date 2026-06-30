from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled

from eventyay.base.models.checkin import CheckinList
from eventyay.base.models.devices import Device
from eventyay.control.forms.event import SafeEventMultipleChoiceField


class CheckinListCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    option_inherits_attrs = False

    def __init__(self, *args, event_ids_by_pk=None, **kwargs):
        self.event_ids_by_pk = event_ids_by_pk or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            pk = str(getattr(value, 'value', value))
            event_id = self.event_ids_by_pk.get(pk)
            if event_id is not None:
                option['attrs'] = dict(option.get('attrs') or {})
                option['attrs']['data-event-id'] = str(event_id)
        return option


class SafeCheckinListMultipleChoiceField(forms.ModelMultipleChoiceField):
    def __init__(self, queryset, *args, **kwargs):
        queryset = queryset.model.objects.none()
        super().__init__(queryset, *args, **kwargs)

    def label_from_instance(self, obj):
        return f'{obj.name} - {obj.event.name}'


class DeviceForm(forms.ModelForm):
    @scopes_disabled()
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer')
        super().__init__(*args, **kwargs)
        published_events = organizer.events.filter(live=True, tickets_published=True)
        self.fields['limit_events'].queryset = published_events.order_by('-has_subevents', '-date_from')
        self.fields['all_events'].label = _('All events (including newly created and published ones)')
        self.fields['gate'].queryset = organizer.gates.all()
        if not self.instance.pk:
            self.fields['security_profile'].initial = 'eventyay_checkin'

        self.fields['security_profile'].help_text = _(
            'Choose the profile that matches how this device will be used in the check-in app. '
            'See the descriptions above the field for details.'
        )
        self.fields['security_profile'].widget.attrs.setdefault('class', 'form-control')

        checkin_list_qs = (
            CheckinList.objects.filter(
                event__organizer=organizer,
                event__live=True,
                event__tickets_published=True,
            )
            .select_related('event')
            .order_by('event__name', 'name')
        )
        self.checkin_list_event_map = {
            str(checkin_list.pk): str(checkin_list.event_id) for checkin_list in checkin_list_qs
        }
        self.fields['limit_checkin_lists'].queryset = checkin_list_qs
        self.fields['limit_checkin_lists'].required = False
        self.fields['limit_checkin_lists'].help_text = _(
            'Only check-in lists for the events selected above are shown.'
        )
        self.fields['limit_checkin_lists'].widget = CheckinListCheckboxSelectMultiple(
            attrs={
                'class': 'scrolling-multiple-choice scrolling-multiple-choice-large device-checkin-lists-widget',
            },
            event_ids_by_pk=self.checkin_list_event_map,
        )
        self.fields['limit_checkin_lists'].widget.choices = self.fields['limit_checkin_lists'].choices

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('all_events') and not cleaned_data.get('limit_events'):
            raise ValidationError(_('Your device will not have access to anything, please select some events.'))

        limit_checkin_lists = cleaned_data.get('limit_checkin_lists')
        if limit_checkin_lists:
            if cleaned_data.get('all_events'):
                allowed_event_ids = set(self.fields['limit_events'].queryset.values_list('pk', flat=True))
            else:
                limit_events = cleaned_data.get('limit_events') or []
                allowed_event_ids = {event.pk for event in limit_events}

            invalid_lists = [checkin_list for checkin_list in limit_checkin_lists if checkin_list.event_id not in allowed_event_ids]
            if invalid_lists:
                raise ValidationError(_('Selected check-in lists must belong to the selected events.'))

        return cleaned_data

    class Meta:
        model = Device
        fields = ['name', 'all_events', 'limit_events', 'security_profile', 'gate', 'limit_checkin_lists']
        widgets = {
            'limit_events': forms.CheckboxSelectMultiple(
                attrs={
                    'data-inverse-dependency': '#id_all_events',
                    'class': 'scrolling-multiple-choice scrolling-multiple-choice-large',
                }
            ),
        }
        field_classes = {
            'limit_events': SafeEventMultipleChoiceField,
            'limit_checkin_lists': SafeCheckinListMultipleChoiceField,
        }
