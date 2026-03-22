"""Czech-specific form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .cz_regions import REGION_CHOICES

birth_number = re.compile(r'^(?P<birth>\d{6})/?(?P<id>\d{3,4})$')
ic_number = re.compile(r'^(?P<number>\d{7})(?P<check>\d)$')


class CZRegionSelect(Select):
    """A select widget widget with list of Czech regions as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class CZPostalCodeField(RegexField):
    """
    A form field that validates its input as Czech postal code.

    Valid form is XXXXX or XXX XX, where X represents integer.
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in the format XXXXX or XXX XX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{5}$|^\d{3} \d{2}$', **kwargs)

    def clean(self, value):
        """
        Validates the input and returns a string that contains only numbers.

        Returns an empty string for empty values.
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value
        return value.replace(' ', '')


class CZBirthNumberField(CharField):
    """Czech birth number form field."""

    default_error_messages = {
        'invalid_format': _('Enter a birth number in the format XXXXXX/XXXX or XXXXXXXXXX.'),
        'invalid': _('Enter a valid birth number.'),
    }

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        match = re.match(birth_number, value)
        if not match:
            raise ValidationError(self.error_messages['invalid_format'], code='invalid_format')

        birth, id = match.groupdict()['birth'], match.groupdict()['id']

        # Three digits for verification number were used until 1. january 1954
        if len(id) == 3 and int(birth[:2]) < 54:
            return '%s' % value

        # Birth number is in format YYMMDD. Females have month value raised by 50.
        # In case that all possible number are already used (for given date),
        # the month field is raised by 20.
        month = int(birth[2:4])
        if (not 1 <= month <= 12) and (not 21 <= month <= 32) and \
                (not 51 <= month <= 62) and (not 71 <= month <= 82):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        day = int(birth[4:6])
        if not (1 <= day <= 31):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # Fourth digit has been added since 1. January 1954.
        # It is modulo of dividing birth number and verification number by 11.
        # If the modulo were 10, the last number was 0 (and therefore, the whole
        # birth number wasn't divisable by 11. These number are no longer used (since 1985)
        # and the condition 'modulo == 10' can be removed in 2085.

        modulo = int(birth + id[:3]) % 11

        if (modulo == int(id[-1])) or (modulo == 10 and id[-1] == '0'):
            return '%s' % value
        else:
            raise ValidationError(self.error_messages['invalid'], code='invalid')


class CZICNumberField(CharField):
    """Czech IC number form field."""

    default_error_messages = {
        'invalid': _('Enter a valid IC number.'),
    }

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        match = re.match(ic_number, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        number, check = match.groupdict()[
            'number'], int(match.groupdict()['check'])

        weighted_sum = 0
        weight = 8
        for digit in number:
            weighted_sum += int(digit) * weight
            weight -= 1

        remainder = weighted_sum % 11

        # remainder is equal:
        #  0 or 10: last digit is 1
        #  1: last digit is 0
        # in other case, last digit is 11 - remainder

        if (not remainder % 10 and check == 1) or \
            (remainder == 1 and check == 0) or \
                (check == (11 - remainder)):
            return '%s' % value

        raise ValidationError(self.error_messages['invalid'], code='invalid')
