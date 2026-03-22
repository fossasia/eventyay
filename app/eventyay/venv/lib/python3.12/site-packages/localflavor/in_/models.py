from django.db import models
from django.utils.translation import gettext_lazy as _

from .forms import INPANCardNumberFormField
from .in_states import STATE_CHOICES
from .validators import INPANCardNumberValidator


class INStateField(models.CharField):
    """
    A model field that stores the two-letter Indian state abbreviation in the database.

    Forms represent it as a ``forms.INStateField`` field.
    """

    description = _("Indian state (two uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs

class INPANCardNumberField(models.CharField):
    """
    A model field that accepts indian PAN Card number.

    Forms represent it as a ``forms.INPANCardNumberFormField`` field.

    .. versionadded:: 4.0
    """
    description = _("PAN Card number field")
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super().__init__(*args, **kwargs)
        self.validators.append(INPANCardNumberValidator())

    def formfield(self, **kwargs):
        defaults = {'form_class': INPANCardNumberFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
