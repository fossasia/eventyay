import re
from datetime import date

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .ee_counties import COUNTY_CHOICES

idcode = re.compile(r'^([1-6])(\d\d)(\d\d)(\d\d)(?:\d{3})(\d)$')
zipcode = re.compile(r'^[1-9]\d{4}$')
bregcode = re.compile(r'^[1-9]\d{7}$')


class EEZipCodeField(RegexField):
    """
    A form field that validates input as a Estonian zip code.

    Valid codes consist of five digits; first digit cannot be 0.
    """

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(zipcode, **kwargs)


class EECountySelect(Select):
    """A Select widget that uses a list of Estonian counties as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=COUNTY_CHOICES)


class EEPersonalIdentificationCode(CharField):
    """A form field that validates input as an Estonian personal identification code.

    See: https://www.riigiteataja.ee/akt/106032012004
    """

    default_error_messages = {
        'invalid_format': _('Enter an 11-digit Estonian personal identification code.'),
        'invalid': _('Enter a valid Estonian personal identification code.'),
    }

    @staticmethod
    def ee_checksum(value):
        """Takes a string of digits as input, returns check digit."""
        for i in (1, 3):
            check = 0
            for c in value:
                check += i * int(c)
                i = (i % 9) + 1
            check %= 11
            if check < 10:
                return check
            # If check==10 then we do another loop starting at i=3

        return check % 10

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(idcode, value)
        if not match:
            raise ValidationError(self.error_messages['invalid_format'], code='invalid_format')

        century, year, month, day, check = map(int, match.groups())

        if check != self.ee_checksum(value[:10]):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Century digit also encodes gender:
        # 1 - male born in 18xx
        # 2 - female born in 18xx
        # 3 - male born in 19xx
        # ...
        year += 1800 + 100 * ((century - 1) // 2)
        try:
            date(year, month, day)
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class EEBusinessRegistryCode(CharField):
    """A form field that validates input as an Estonian business registration code.

    .. versionadded:: 1.2
    """

    default_error_messages = {
        'invalid_format': _('Enter an 8-digit Estonian business registry code.'),
        'invalid': _('Enter a valid Estonian business registry code.'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(bregcode, value)
        if not match:
            raise ValidationError(self.error_messages['invalid_format'], code='invalid_format')

        check = int(value[7])

        if check != EEPersonalIdentificationCode.ee_checksum(value[:7]):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value
