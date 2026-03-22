"""Spanish-specific Form helpers."""

import re

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .es_provinces import PROVINCE_CHOICES
from .es_regions import REGION_CHOICES


class ESPostalCodeField(RegexField):
    """
    A form field that validates its input as a spanish postal code.

    Spanish postal code is a five digits string, with two first digits
    between 01 and 52, assigned to provinces code.
    """

    default_error_messages = {
        'invalid': _('Enter a valid postal code in the range and format 01XXX - 52XXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^(0[1-9]|[1-4][0-9]|5[0-2])\d{3}$', **kwargs)


class ESIdentityCardNumberField(RegexField):
    """
    Spanish NIF/NIE/CIF (Fiscal Identification Number) code.

    Validates three different formats:

        NIF (individuals): 12345678A
        CIF (companies): A12345678
        NIE (foreigners): X12345678A

    according to a couple of simple checksum algorithms.

    Value can include a space or hyphen separator between number and letters.
    Number length is not checked for NIF (or NIE), old values start with a 1,
    and future values can contain digits greater than 8. The CIF control digit
    can be a number or a letter depending on company type. Algorithm is not
    public, and different authors have different opinions on which ones allows
    letters, so both validations are assumed true for all types.

    http://es.wikipedia.org/wiki/N%C3%BAmero_de_identificaci%C3%B3n_fiscal

    .. versionchanged:: 1.1

    """

    default_error_messages = {
        'invalid': _('Please enter a valid NIF, NIE, or CIF.'),
        'invalid_only_nif': _('Please enter a valid NIF or NIE.'),
        'invalid_nif': _('Invalid checksum for NIF.'),
        'invalid_nie': _('Invalid checksum for NIE.'),
        'invalid_cif': _('Invalid checksum for CIF.'),
    }

    def __init__(self, only_nif=False, **kwargs):
        self.only_nif = only_nif
        self.nif_control = 'TRWAGMYFPDXBNJZSQVHLCKE'
        self.cif_control = 'JABCDEFGHI'
        self.cif_types = 'ABCDEFGHJKLMNPQRSUVW'
        self.nie_types = 'XYZ'
        self.id_card_pattern = r'^([%s]?)[ -]?(\d+)[ -]?([%s]?)$'
        id_card_re = re.compile(self.id_card_pattern %
                                (self.cif_types + self.nie_types,
                                 self.nif_control + self.cif_control),
                                re.IGNORECASE)

        error_messages = {
            'invalid': self.default_error_messages['invalid%s' % (self.only_nif and '_only_nif' or '')]
        }
        error_messages.update(kwargs.get('error_messages', {}))
        kwargs['error_messages'] = error_messages

        super().__init__(id_card_re, **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = value.upper().replace(' ', '').replace('-', '')
        m = re.match(self.id_card_pattern %
                     (self.cif_types + self.nie_types,
                      self.nif_control + self.cif_control),
                     value)
        letter1, number, letter2 = m.groups()

        if not letter1 and letter2:
            # NIF
            if letter2 == self.nif_get_checksum(number):
                return value
            else:
                raise ValidationError(self.error_messages['invalid_nif'], code='invalid_nif')
        elif letter1 in self.nie_types and letter2:
            # NIE
            if letter2 == self.nif_get_checksum(str(self.nie_types.index(letter1)) + number):
                return value
            else:
                raise ValidationError(self.error_messages['invalid_nie'], code='invalid_nie')
        elif not self.only_nif and letter1 in self.cif_types and len(number) in [7, 8]:
            # CIF
            if not letter2:
                number, letter2 = number[:-1], int(number[-1])
            checksum = cif_get_checksum(number)
            if letter2 in (checksum, self.cif_control[checksum]):
                return value
            else:
                raise ValidationError(self.error_messages['invalid_cif'], code='invalid_cif')
        else:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

    def nif_get_checksum(self, d):
        return self.nif_control[int(d) % 23]


class ESCCCField(RegexField):
    """
    A form field that validates its input as a Spanish bank account or CCC (Codigo Cuenta Cliente).

        Spanish CCC is in format EEEE-OOOO-CC-AAAAAAAAAA where:

            E = entity
            O = office
            C = checksum
            A = account

        It's also valid to use a space as delimiter, or to use no delimiter.

        First checksum digit validates entity and office, and last one
        validates account. Validation is done multiplying every digit of 10
        digit value (with leading 0 if necessary) by number in its position in
        string 1, 2, 4, 8, 5, 10, 9, 7, 3, 6. Sum resulting numbers and extract
        it from 11.  Result is checksum except when 10 then is 1, or when 11
        then is 0.
    """

    default_error_messages = {
        'invalid': _('Please enter a valid bank account number in format XXXX-XXXX-XX-XXXXXXXXXX.'),
        'checksum': _('Invalid checksum for bank account number.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{4}[ -]?\d{4}[ -]?\d{2}[ -]?\d{10}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        m = re.match(r'^(\d{4})[ -]?(\d{4})[ -]?(\d{2})[ -]?(\d{10})$', value)
        entity, office, checksum, account = m.groups()
        if get_checksum('00' + entity + office) + get_checksum(account) == checksum:
            return value
        else:
            raise ValidationError(self.error_messages['checksum'], code='checksum')


def get_checksum(d):
    control_str = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]
    digits = [int(digit) * int(control) for digit, control in zip(d, control_str)]
    return str(11 - sum(digits) % 11).replace('10', '1').replace('11', '0')


class ESRegionSelect(Select):
    """A Select widget that uses a list of spanish regions as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class ESProvinceSelect(Select):
    """A Select widget that uses a list of spanish provinces as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCE_CHOICES)


def cif_get_checksum(number):
    s1 = sum([int(digit) for pos, digit in enumerate(number) if int(pos) % 2])
    s2 = sum([sum([int(unit) for unit in str(int(digit) * 2)])
             for pos, digit in enumerate(number) if not int(pos) % 2])
    return (10 - ((s1 + s2) % 10)) % 10
