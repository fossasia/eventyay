from django import forms
from django.contrib.auth.models import AnonymousUser
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

    def __init__(self, data=None, files=None, user: AnonymousUser | User | None = None, **kwargs):
        super().__init__(data, files, **kwargs)

        if user and user.is_authenticated:
            # Query distinct events based on the user's orders
            queryset = Event.objects.annotate(lower_email=Lower('orders__email'))
            events = queryset.filter(lower_email__in=user.email_addresses).distinct()
            self.fields['event'].queryset = events
