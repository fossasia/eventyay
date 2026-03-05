from typing import cast

from django import forms
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, User


class UserOrderFilterForm(forms.Form):
    event = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label=_('Event'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label=_('Select an Event'),
    )

    def __init__(self, *args, **kwargs):
        user = cast(User | None, kwargs.pop('user', None))  # Get the user from the kwargs
        super().__init__(*args, **kwargs)

        if user:
            # Query distinct events based on the user's orders.
            # user.email_addresses already provides lowercase emails.
            events = Event.objects.annotate(order_email=Lower('orders__email')).filter(order_email__in=user.email_addresses)
            self.fields['event'].queryset = events.distinct()


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
            # user.email_addresses already provides lowercase emails.
            events = Event.objects.annotate(speaker_email=Lower('submissions__speakers__email'))
            events = events.filter(speaker_email__in=user.email_addresses)
            self.fields['event'].queryset = events.distinct()
