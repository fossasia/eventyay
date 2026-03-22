"""Romanian specific form helpers."""
import datetime

from django.forms import CharField, RegexField, Select, ValidationError
from django.utils.translation import gettext_lazy as _

from .ro_counties import COUNTIES_CHOICES


class ROCIFField(RegexField):
    """
    A Romanian fiscal identity code (CIF) field.

    For CIF validation algorithm see: https://ro.wikipedia.org/wiki/Cod_de_Identificare_Fiscal%C4%83
    """

    default_error_messages = {
        'invalid': _("Enter a valid CIF."),
    }

    def __init__(self, max_length=10, min_length=2, **kwargs):
        super().__init__(
            r'^(RO)?[0-9]{2,10}', max_length=max_length, min_length=min_length,
            **kwargs
        )

    def clean(self, value):
        """
        CIF validation.

        Args:
            value: the CIF code
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value

        value = value.strip()

        # strip RO part
        if value[0:2] == 'RO':
            value = value[2:]

        key = '753217532'[::-1]
        value = value[::-1]
        key_iter = iter(key)
        checksum = 0

        for digit in value[1:]:
            checksum += int(digit) * int(next(key_iter))

        checksum = checksum * 10 % 11

        if checksum == 10:
            checksum = 0

        if checksum != int(value[0]):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value[::-1]


class ROCNPField(RegexField):
    """
    A Romanian personal identity code (CNP) field.

    For CNP validation algorithm see: https://ro.wikipedia.org/wiki/Cod_numeric_personal
    """

    default_error_messages = {
        'invalid': _("Enter a valid CNP."),
    }

    def __init__(self, max_length=13, min_length=13, **kwargs):
        super().__init__(
            r'^[1-9][0-9]{12}', max_length=max_length, min_length=min_length,
            **kwargs
        )

    def clean(self, value):
        """
        CNP validations.

        Args:
            value: the CNP code
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value

        # check birthdate digits
        try:
            # parse using the format YYMMDD
            datetime.datetime.strptime(value[1:7], '%y%m%d')
        except ValueError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        # checksum
        key = '279146358279'
        checksum = 0
        value_iter = iter(value)

        for digit in key:
            checksum += int(digit) * int(next(value_iter))

        checksum %= 11

        if checksum == 10:
            checksum = 1

        if checksum != int(value[12]):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class ROCountyField(CharField):
    """
    A form field that validates its input is a Romanian county name or abbreviation.

    It normalizes the input to the standard vehicle registration abbreviation for the given county.

    WARNING: This field will only accept names written with diacritics (using comma bellow for ș and ț); consider
    using ROCountySelect if this behavior is unacceptable for you

    For more information regarding diacritics see *Comma-below (ș and ț) versus cedilla (ş and ţ)* and
    *Unicode and HTML* sections from: `Romanian alphabet <https://en.wikipedia.org/wiki/Romanian_alphabet>`_.

    Example:
        | Argeș => valid (comma bellow)
        | Argeş => invalid (cedilla)
        | Arges => invalid (no diacritic)

    """

    default_error_messages = {
        'invalid': 'Enter a Romanian county code or name.',
    }

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        value = value.upper()

        # search for county code
        for entry in COUNTIES_CHOICES:
            if value in entry:
                return value

        # search for county name
        normalized_cc = []
        for entry in COUNTIES_CHOICES:
            normalized_cc.append((entry[0], entry[1].upper()))

        for entry in normalized_cc:
            if entry[1] == value:
                return entry[0]

        raise ValidationError(self.error_messages['invalid'], code='invalid')


class ROCountySelect(Select):
    """A Select widget that uses a list of Romanian counties (județe) as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=COUNTIES_CHOICES)


class ROPostalCodeField(RegexField):
    """Romanian postal code field."""

    default_error_messages = {
        'invalid': _('Enter a valid postal code in the format XXXXXX'),
    }

    def __init__(self, max_length=6, min_length=6, **kwargs):
        super().__init__(
            r'^[0-9][0-8][0-9]{4}$', max_length=max_length,
            min_length=min_length, **kwargs
        )
