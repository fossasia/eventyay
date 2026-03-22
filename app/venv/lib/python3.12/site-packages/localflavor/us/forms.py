"""USA-specific Form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

ssn_re = re.compile(r"^(?P<area>\d{3})[-\ ]?(?P<group>\d{2})[-\ ]?(?P<serial>\d{4})$")


class USZipCodeField(RegexField):
    """
    A form field that validates input as a U.S. ZIP code.

    Valid formats are XXXXX or XXXXX-XXXX.

    .. note::

        If you are looking for a form field with a list of U.S. Postal Service
        locations please use :class:`~localflavor.us.forms.USPSSelect`.

    .. versionadded:: 1.1

    Whitespace around the ZIP code is accepted and automatically trimmed.
    """

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXX or XXXXX-XXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{5}(?:-\d{4})?$', **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return value.strip()


class USSocialSecurityNumberField(CharField):
    """
    A United States Social Security number.

    Checks the following rules to determine whether the number is valid:

        * Conforms to the XXX-XX-XXXX format.
        * No group consists entirely of zeroes.
        * The leading group is not "666" (block "666" will never be allocated).
        * The number is not in the promotional block 987-65-4320 through
          987-65-4329, which are permanently invalid.
        * The number is not one known to be invalid due to otherwise widespread
          promotional use or distribution (e.g., the Woolworth's number or the
          1962 promotional number).

    .. versionadded:: 1.1
    """

    default_error_messages = {
        'invalid': _('Enter a valid U.S. Social Security number in XXX-XX-XXXX format.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        match = re.match(ssn_re, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        area, group, serial = match.groupdict()['area'], match.groupdict()['group'], match.groupdict()['serial']

        # First pass: no blocks of all zeroes.
        if area == '000' or group == '00' or serial == '0000':
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Second pass: promotional and otherwise permanently invalid numbers.
        # pylint: disable=too-many-boolean-expressions
        if (area == '666' or
                area.startswith('9') or
                (area == '078' and group == '05' and serial == '1120') or
                (area == '219' and group == '09' and serial == '9999')):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return '%s-%s-%s' % (area, group, serial)


class USStateField(CharField):
    """
    A form field that validates its input is a U.S. state, territory, or COFA territory.
    The input is validated against a dictionary which includes names and abbreviations.

    It normalizes the input to the standard two-letter postal service
    abbreviation for the given state.
    """

    default_error_messages = {
        'invalid': _('Enter a U.S. state or territory.'),
    }

    def clean(self, value):
        from .us_states import STATES_NORMALIZED
        value = super().clean(value)
        if value in self.empty_values:
            return value
        try:
            return STATES_NORMALIZED[value.lower()]
        except KeyError:
            pass
        raise ValidationError(self.error_messages['invalid'], code='invalid')


class USStateSelect(Select):
    """A Select widget that uses a list of U.S. states/territories as its choices."""

    def __init__(self, attrs=None):
        from .us_states import STATE_CHOICES
        super().__init__(attrs, choices=STATE_CHOICES)


class USPSSelect(Select):
    """
    A Select widget that uses a list of US Postal Service codes as its choices.

    .. note::

        If you are looking for a form field that validates U.S. ZIP codes
        please use :class:`~localflavor.us.forms.USZipCodeField`.

    """

    def __init__(self, attrs=None):
        from .us_states import USPS_CHOICES
        super().__init__(attrs, choices=USPS_CHOICES)
