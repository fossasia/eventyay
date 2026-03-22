from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from . import forms
from .pk_states import STATE_CHOICES


class PKStateField(CharField):
    """
    A model field that stores the five-letter Pakistani state abbreviation in the database.

    It is represented with :data:`~localflavor.pk.pk_states.STATE_CHOICES`` choices.
    """

    description = _("Pakistani State")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class PKPostCodeField(CharField):
    """
    A model field that stores the five-digit Pakistani postcode in the database

    Forms represent it as a :class:`~localflavor.pk.forms.PKPostCodeField` field.
    """

    description = _("Pakistani Postcode")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': forms.PKPostCodeField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
