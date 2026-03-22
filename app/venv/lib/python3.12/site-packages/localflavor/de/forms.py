"""DE-specific Form helpers."""

import re

from django.core.exceptions import ImproperlyConfigured
from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .de_states import STATE_CHOICES

ID_RE = re.compile(r"^(?P<residence>\d{10})(?P<origin>\w{1,3})"
                   r"[-\ ]?(?P<birthday>\d{7})[-\ ]?(?P<validity>\d{7})"
                   r"[-\ ]?(?P<checksum>\d{1})$")


class DEZipCodeField(RegexField):
    """A form field that validates input as a German zip code.

    Valid zip codes consist of five digits.
    """

    default_error_messages = {
        'invalid': _('Enter a zip code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^([0]{1}[1-9]{1}|[1-9]{1}[0-9]{1})[0-9]{3}$', **kwargs)


class DEStateSelect(Select):
    """A Select widget that uses a list of DE states as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)


class DEIdentityCardNumberField(CharField):
    """A German identity card number.

    Checks the following rules to determine whether the number is valid:

        * Conforms to the XXXXXXXXXXX-XXXXXXX-XXXXXXX-X format.
        * No group consists entirely of zeroes.
        * Included checksums match calculated checksums

    Algorithm is documented at http://de.wikipedia.org/wiki/Personalausweis
    """

    default_error_messages = {
        'invalid': _('Enter a valid German identity card number in '
                     'XXXXXXXXXXX-XXXXXXX-XXXXXXX-X format.'),
    }

    def has_valid_checksum(self, number):
        given_number, given_checksum = number[:-1], number[-1]
        calculated_checksum = 0
        parameter = 7

        for item in given_number:
            fragment = str(int(item) * parameter)
            if fragment.isalnum():
                calculated_checksum += int(fragment[-1])
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
        match = re.match(ID_RE, value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        id_parts = match.groupdict()
        residence = id_parts['residence']
        origin = id_parts['origin']
        birthday = id_parts['birthday']
        validity = id_parts['validity']
        checksum = id_parts['checksum']

        if (residence == '0000000000' or
                birthday == '0000000' or
                validity == '0000000'):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        all_digits = "%s%s%s%s" % (residence, birthday, validity, checksum)
        if (not self.has_valid_checksum(residence) or
                not self.has_valid_checksum(birthday) or
                not self.has_valid_checksum(validity) or
                not self.has_valid_checksum(all_digits)):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return '%s%s-%s-%s-%s' % (residence,
                                  origin,
                                  birthday,
                                  validity,
                                  checksum)
