"""South Africa-specific Form helpers."""
import re
from datetime import date

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _
from stdnum import luhn

id_re = re.compile(r'^(?P<yy>\d\d)(?P<mm>\d\d)(?P<dd>\d\d)(?P<mid>\d{4})(?P<end>\d{3})')


class ZAIDField(CharField):
    """
    A form field for South African ID numbers.

    The checksum is validated using the Luhn checksum, and uses a simplistic (read: not entirely accurate)
    check for the birth date.
    """

    default_error_messages = {
        'invalid': _('Enter a valid South African ID number'),
    }

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        # strip spaces and dashes
        value = value.replace(' ', '').replace('-', '')

        match = re.match(id_re, value)

        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        g = match.groupdict()

        try:
            # The year 2000 is conveniently a leapyear.
            # This algorithm will break in xx00 years which aren't leap years
            # There is no way to guess the century of a ZA ID number
            date(int(g['yy']) + 2000, int(g['mm']), int(g['dd']))
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        if not luhn.is_valid(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class ZAPostCodeField(RegexField):
    """
    A form field that validates input as a South African postcode.

    Valid postcodes must have four digits.
    """

    default_error_messages = {
        'invalid': _('Enter a valid South African postal code'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{4}$', **kwargs)


class ZAProvinceSelect(Select):
    """A Select widget that uses a list of South African Provinces as its choices."""

    def __init__(self, attrs=None):
        from .za_provinces import PROVINCE_CHOICES
        super().__init__(attrs, choices=PROVINCE_CHOICES)
