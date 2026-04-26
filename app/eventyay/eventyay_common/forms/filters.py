from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event


class UserOrderFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the kwargs
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if user:
            selected_event = self.get_visible_selected_event(user, request)
            event_filter = Q(orders__email__iexact=user.email)
            if selected_event:
                event_filter |= Q(pk=selected_event.pk)
            self.fields['event'].queryset = Event.objects.filter(event_filter).distinct()

    def get_visible_selected_event(self, user, request):
        event_id = self.data.get(self.add_prefix('event')) if self.is_bound else None
        if not event_id:
            return None
        try:
            event_pk = int(event_id)
        except (TypeError, ValueError):
            return None

        event = Event.objects.select_related('organizer').filter(pk=event_pk).first()
        if not event:
            return None

        if (
            (event.live and event.is_public)
            or user.has_event_permission(event.organizer, event, request=request)
        ):
            return event
        return None


class SessionsFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )

    search = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by session name')})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Query distinct events based on the user's proposals
            events = Event.objects.filter(submissions__speakers__email__iexact=user.email).distinct()
            self.fields['event'].queryset = events
