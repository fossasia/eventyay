"""Swiss-specific Form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured
from django.core.validators import RegexValidator
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from ..generic import validators
from .ch_states import STATE_CHOICES

zip_re = re.compile(r'^[1-9]\d{3}$')
id_re = re.compile(r'^(?P<idnumber>\w{8})(?P<pos9>(\d{1}|<))(?P<checksum>\d{1})$')
ssn_re = re.compile(r'^756.\d{4}\.\d{4}\.\d{2}$')


class CHZipCodeField(RegexField):
    """
    A form field that validates input as a Swiss zip code.

    Valid codes consist of four digits ranging from 1XXX to 9XXX.

    See:
    http://en.wikipedia.org/wiki/Postal_codes_in_Switzerland_and_Liechtenstein
    """

    default_error_messages = {
        'invalid': _('Enter a valid postal code in the range and format 1XXX - 9XXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(zip_re, **kwargs)


class CHStateSelect(Select):
    """A Select widget that uses a list of CH states as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)


class CHIdentityCardNumberField(CharField):
    """
    A Swiss identity card number.

    Checks the following rules to determine whether the number is valid:

        * Conforms to the X1234567<0 or 1234567890 format.
        * Included checksums match calculated checksums

    """

    default_error_messages = {
        'invalid': _('Enter a valid Swiss identity or passport card number in X1234567<0 or 1234567890 format.'),
    }

    def has_valid_checksum(self, number):
        given_number, given_checksum = number[:-1], number[-1]
        new_number = given_number
        calculated_checksum = 0
        parameter = 7

        first = str(number[:1])
        if first.isalpha():
            num = ord(first.upper()) - 65
            if num < 0 or num > 8:
                return False
            new_number = str(num) + new_number[1:]
            new_number = new_number[:8] + '0'

        if not new_number.isdigit():
            return False

        for digit in new_number:
            fragment = int(digit) * parameter
            calculated_checksum += fragment

            if parameter == 1:
                parameter = 7
            elif parameter == 3:
                parameter = 1
            elif parameter == 7:
                parameter = 3

        return str(calculated_checksum)[-1] == given_checksum

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = re.match(id_re, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        result = match.groupdict()
        idnumber, pos9, checksum = result['idnumber'], result['pos9'], result['checksum']

        if idnumber in ('00000000', 'A0000000'):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        all_digits = "%s%s%s" % (idnumber, pos9, checksum)
        if not self.has_valid_checksum(all_digits):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s%s%s' % (idnumber, pos9, checksum)


class CHSocialSecurityNumberField(CharField):
    """
    A Swiss Social Security number (also known as the new AHV Number).

    Checks the following rules to determine whether the number is valid:

        * Conforms to the 756.XXXX.XXXX.XX
        * Included checksums match calculated checksums

    See:
    http://de.wikipedia.org/wiki/Sozialversicherungsnummer#Versichertennummer

    .. versionadded:: 1.2
    """

    default_error_messages = {
        'invalid': _('Enter a valid Swiss Social Security number in 756.XXXX.XXXX.XX format.'),
    }
    default_validators = [
        RegexValidator(regex=ssn_re),
        validators.EANValidator(strip_nondigits=True),
    ]

    def run_validators(self, value):
        try:
            super().run_validators(value)
        except ValidationError as errs:
            # Deduplicate error messages, if any
            raise ValidationError(list(set(errs.messages)), code='invalid')
