"""FI-specific Form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .fi_municipalities import MUNICIPALITY_CHOICES


class FIZipCodeField(RegexField):
    """
    A form field that validates input as a Finnish zip code.

    Valid codes consist of five digits.
    """

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{5}$', **kwargs)


class FIMunicipalitySelect(Select):
    """A Select widget that uses a list of Finnish municipalities as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=MUNICIPALITY_CHOICES)


class FISocialSecurityNumber(CharField):
    """A form field that validates input as a Finnish social security number."""

    default_error_messages = {
        'invalid': _('Enter a valid Finnish social security number.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        checkmarks = "0123456789ABCDEFHJKLMNPRSTUVWXY"
        result = re.match(r"""^
            (?P<date>([0-2]\d|3[01])
            (0\d|1[012])
            (\d{2}))
            [ABCDEFUVWXY+\-]
            (?P<serial>(\d{3}))
            (?P<checksum>[%s])$""" % checkmarks, value, re.VERBOSE | re.IGNORECASE)
        if not result:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        gd = result.groupdict()
        checksum = int(gd['date'] + gd['serial'])
        if checkmarks[checksum % len(checkmarks)] == gd['checksum'].upper():
            return '%s' % value.upper()
        raise ValidationError(self.error_messages['invalid'], code='invalid')
