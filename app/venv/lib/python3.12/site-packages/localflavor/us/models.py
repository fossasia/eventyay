from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .forms import USSocialSecurityNumberField as USSocialSecurityNumberFieldFormField
from .forms import USZipCodeField as USZipCodeFormField
from .us_states import STATE_CHOICES, USPS_CHOICES


class USStateField(CharField):
    """
    A model field that stores the two-letter U.S. state abbreviation in the database.

    Forms represent it as a ``forms.USStateField`` field.
    """

    description = _("U.S. state (two uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = STATE_CHOICES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class USPostalCodeField(CharField):
    """
    A model field that stores the two-letter U.S. Postal Service abbreviation in the database.

    Forms represent it as a :class:`~localflavor.us.forms.USPSSelect`` field.

    .. note::

        If you are looking for a model field that validates U.S. ZIP codes
        please use :class:`~localflavor.us.models.USZipCodeField`.
    """

    description = _("U.S. postal code (two uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = USPS_CHOICES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class USZipCodeField(CharField):
    """
    A model field that stores the U.S. ZIP code in the database.

    Forms represent it as a :class:`~localflavor.us.forms.USZipCodeField` field.

    .. note::

        If you are looking for a model field with a list of U.S. Postal Service
        locations please use :class:`~localflavor.us.models.USPostalCodeField`.

    .. versionadded:: 1.1

    """

    description = _("U.S. ZIP code")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': USZipCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class USSocialSecurityNumberField(CharField):
    """
    A model field that stores  the security number in the format ``XXX-XX-XXXX``.

    Forms represent it as ``forms.USSocialSecurityNumberField`` field.

    .. versionadded:: 1.1
    """

    description = _("Social security number")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': USSocialSecurityNumberFieldFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
