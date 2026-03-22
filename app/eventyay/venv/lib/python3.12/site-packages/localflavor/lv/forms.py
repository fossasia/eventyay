import re
from datetime import date
import warnings

from django.forms import ValidationError
from django.forms.fields import CharField, Select
from django.utils.translation import gettext_lazy as _

from .lv_choices import MUNICIPALITY_CHOICES

zipcode = re.compile(r'^(LV\s?-\s?)?(?P<code>[1-5]\d{3})$', re.IGNORECASE)
idcode = re.compile(r'^(\d\d)(\d\d)(\d\d)-([0-2])(?:\d{3})(\d)$')


class LVPostalCodeField(CharField):
    """
    A form field that validates and normalizes Latvian postal codes.

    Latvian postal codes in following forms accepted:
        * XXXX
        * LV-XXXX
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in the format XXXX or LV-XXXX.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(zipcode, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return 'LV-' + match.group('code')


class LVMunicipalitySelect(Select):
    """A select field of Latvian municipalities."""

    def __init__(self, attrs=None):
        warnings.warn("Choices have changed for LVMunicipalitySelect in localflavor 5.0. See changelog for details.")
        super().__init__(attrs, choices=MUNICIPALITY_CHOICES)


class LVPersonalCodeField(CharField):
    """A form field that validates input as a Latvian personal code."""

    default_error_messages = {
        'invalid_format': _('Enter a Latvian personal code in format XXXXXX-XXXXX.'),
        'invalid': _('Enter a valid Latvian personal code.'),
    }

    @staticmethod
    def lv_checksum(value):
        """Takes a string of 10 digits as input, returns check digit."""
        multipliers = (1, 6, 3, 7, 9, 10, 5, 8, 4, 2)

        check = sum(mult * int(c) for mult, c in zip(multipliers, value))
        return ((1 - check) % 11) % 10

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(idcode, value)
        if not match:
            raise ValidationError(self.error_messages['invalid_format'], code='invalid_format')

        day, month, year, century, check = map(int, match.groups())

        if check != self.lv_checksum(value[0:6] + value[7:11]):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        year += 1800 + 100 * century
        try:
            date(year, month, day)
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value
