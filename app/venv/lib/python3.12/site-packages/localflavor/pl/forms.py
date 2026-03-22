"""Polish-specific form helpers."""

import datetime
import re

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .pl_administrativeunits import ADMINISTRATIVE_UNIT_CHOICES
from .pl_voivodeships import VOIVODESHIP_CHOICES


class PLProvinceSelect(Select):
    """A select widget with list of Polish administrative provinces as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=VOIVODESHIP_CHOICES)


class PLCountySelect(Select):
    """A select widget with list of Polish administrative units as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=ADMINISTRATIVE_UNIT_CHOICES)


class PLPESELField(RegexField):
    """
    A form field that validates as Polish Identification Number (PESEL).

    Checks the following rules:
        * the length consist of 11 digits
        * has a valid checksum
        * contains a valid birth date

    The algorithm is documented at http://en.wikipedia.org/wiki/PESEL.

    .. versionchanged:: 1.4
    """

    default_error_messages = {
        'invalid': _('National Identification Number consists of 11 digits.'),
        'checksum': _('Wrong checksum for the National Identification Number.'),
        'birthdate': _('The National Identification Number contains an invalid birth date.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{11}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not self.has_valid_checksum(value):
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        if not self.has_valid_birth_date(value):
            raise ValidationError(self.error_messages['birthdate'], code='birthdate')
        return '%s' % value

    def has_valid_checksum(self, number):
        """Calculates a checksum with the provided algorithm."""
        multiple_table = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3, 1)
        result = 0
        for i, digit in enumerate(number):
            result += int(digit) * multiple_table[i]
        return result % 10 == 0

    def has_valid_birth_date(self, number):
        """
        Checks whether the birth date encoded in PESEL is valid.
        """
        y = int(number[:2])
        m = int(number[2:4])
        d = int(number[4:6])
        md2century = {80: 1800, 0: 1900, 20: 2000, 40: 2100, 60: 2200}
        for md, cent in md2century.items():
            if 1 <= m - md <= 12:
                y += cent
                m -= md
                break
        try:
            self.birth_date = datetime.date(y, m, d)
            return True
        except ValueError:
            return False


class PLNationalIDCardNumberField(RegexField):
    """
    A form field that validates as Polish National ID Card Number.

    Checks the following rules:
        * the length consist of 3 letter and 6 digits
        * has a valid checksum

    The algorithm is documented at http://en.wikipedia.org/wiki/Polish_identity_card.
    """

    default_error_messages = {
        'invalid': _('National ID Card Number consists of 3 letters and 6 digits.'),
        'checksum': _('Wrong checksum for the National ID Card Number.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^[A-Za-z]{3}\d{6}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = value.upper()

        if not self.has_valid_checksum(value):
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return '%s' % value

    def has_valid_checksum(self, number):
        """Calculates a checksum with the provided algorithm."""
        letter_dict = {'A': 10, 'B': 11, 'C': 12, 'D': 13,
                       'E': 14, 'F': 15, 'G': 16, 'H': 17,
                       'I': 18, 'J': 19, 'K': 20, 'L': 21,
                       'M': 22, 'N': 23, 'O': 24, 'P': 25,
                       'Q': 26, 'R': 27, 'S': 28, 'T': 29,
                       'U': 30, 'V': 31, 'W': 32, 'X': 33,
                       'Y': 34, 'Z': 35}

        # convert letters to integer values
        int_table = [(not c.isdigit()) and letter_dict[c] or int(c)
                     for c in number]

        multiple_table = (7, 3, 1, -1, 7, 3, 1, 7, 3)
        result = 0
        for i, digit in enumerate(int_table):
            result += int(digit) * multiple_table[i]

        return result % 10 == 0


class PLNIPField(RegexField):
    """
    A form field that validates as Polish Tax Number (NIP).

    Valid forms are: XXX-YYY-YY-YY, XXX-YY-YY-YYY or XXXYYYYYYY.
    Checksum algorithm based on documentation at
    http://wipos.p.lodz.pl/zylla/ut/nip-rego.html
    """

    default_error_messages = {
        'invalid': _('Enter a tax number field (NIP) in the format XXX-XXX-XX-XX, XXX-XX-XX-XXX or XXXXXXXXXX.'),
        'checksum': _('Wrong checksum for the Tax Number (NIP).'),
    }

    def __init__(self, **kwargs):
        super().__init__(
            r'^\d{3}-\d{3}-\d{2}-\d{2}$|^\d{3}-\d{2}-\d{2}-\d{3}$|^\d{10}$',
            **kwargs
        )

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value = re.sub("[-]", "", value)
        if not self.has_valid_checksum(value):
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return '%s' % value

    def has_valid_checksum(self, number):
        """Calculates a checksum with the provided algorithm."""
        multiple_table = (6, 5, 7, 2, 3, 4, 5, 6, 7)
        result = 0
        for i, digit in enumerate(number[:-1]):
            result += int(digit) * multiple_table[i]

        result %= 11
        return result == int(number[-1])


class PLREGONField(RegexField):
    """
    A form field that validates its input is a REGON number.

    Valid regon number consists of 9 or 14 digits.
    See http://www.stat.gov.pl/bip/regon_ENG_HTML.htm for more information.
    """

    default_error_messages = {
        'invalid': _('National Business Register Number (REGON) consists of 9 or 14 digits.'),
        'checksum': _('Wrong checksum for the National Business Register Number (REGON).'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{9,14}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not self.has_valid_checksum(value):
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return '%s' % value

    def has_valid_checksum(self, number):
        """Calculates a checksum with the provided algorithm."""
        weights = (
            (8, 9, 2, 3, 4, 5, 6, 7, -1),
            (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8, -1),
            (8, 9, 2, 3, 4, 5, 6, 7, -1, 0, 0, 0, 0, 0),
        )

        weights = [table for table in weights if len(table) == len(number)]

        for table in weights:
            checksum = sum([int(n) * w for n, w in zip(number, table)])

            mod_result = checksum % 11

            if mod_result == 10 and number[-1] != '0':
                return False

            if mod_result % 10:
                return False

        return bool(weights)


class PLPostalCodeField(RegexField):
    """
    A form field that validates as Polish postal code.

    Valid code is XX-XXX where X is digit.
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in the format XX-XXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{2}-\d{3}$', **kwargs)
