"""AR-specific Form helpers."""

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _
from stdnum.ar import cbu
from stdnum.exceptions import InvalidChecksum, InvalidLength
from stdnum.exceptions import ValidationError as StdnumValidationError

from .ar_provinces import PROVINCE_CHOICES


class ARProvinceSelect(Select):
    """A Select widget that uses a list of Argentinean provinces/autonomous cities as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCE_CHOICES)


class ARPostalCodeField(RegexField):
    """
    A field that accepts a 'classic' NNNN Postal Code or a CPA.

    See:

    * http://www.correoargentino.com.ar/cpa/que_es
    * http://www.correoargentino.com.ar/cpa/como_escribirlo
    """

    default_error_messages = {
        'invalid': _("Enter a postal code in the format NNNN or ANNNNAAA."),
    }

    def __init__(self, max_length=8, min_length=4, **kwargs):
        super().__init__(
            r'^\d{4}$|^[A-HJ-NP-Za-hj-np-z]\d{4}\D{3}$',
            max_length=max_length, min_length=min_length, **kwargs
        )

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if len(value) not in (4, 8):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if len(value) == 8:
            return '%s%s%s' % (value[0].upper(), value[1:5], value[5:].upper())
        return value


class ARDNIField(CharField):
    """A field that validates 'Documento Nacional de Identidad' (DNI) numbers."""

    default_error_messages = {
        'invalid': _("This field requires only numbers."),
        'max_digits': _("This field requires 7 or 8 digits."),
    }

    def __init__(self, max_length=10, min_length=7, **kwargs):
        super().__init__(max_length=max_length, min_length=min_length, **kwargs)

    def clean(self, value):
        """Value can be a string either in the [X]X.XXX.XXX or [X]XXXXXXX formats."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not value.isdigit():
            value = value.replace('.', '')
        if not value.isdigit():
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if len(value) not in (7, 8):
            raise ValidationError(self.error_messages['max_digits'], code='max_digits')

        return value


class ARCUITField(RegexField):
    """
    This field validates a CUIT (Código Único de Identificación Tributaria).

    A CUIT is of the form XX-XXXXXXXX-V. The last digit is a check digit.

    More info:
    http://es.wikipedia.org/wiki/Clave_%C3%9Anica_de_Identificaci%C3%B3n_Tributaria

    Info in English:
    http://www.justlanded.com/english/Argentina/Argentina-Guide/Visas-Permits/Other-Legal-Documents

    .. versionchanged:: 2.1

        ``ARCUITField`` now also accepts CUIT with prefix 34.
    """

    default_error_messages = {
        'invalid': _('Enter a valid CUIT in XX-XXXXXXXX-X or XXXXXXXXXXXX format.'),
        'checksum': _("Invalid CUIT."),
        'legal_type': _('Invalid legal type. Type must be 27, 20, 30, 23, 24, 33 or 34.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{2}-?\d{8}-?\d$', **kwargs)

    def clean(self, value):
        """Value can be either a string in the format XX-XXXXXXXX-X or an 11-digit number."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value, cd = self._canon(value)
        if not value[:2] in ['27', '20', '30', '23', '24', '33', '34']:
            raise ValidationError(self.error_messages['legal_type'], code='legal_type')
        if self._calc_cd(value) != cd:
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return self._format(value, cd)

    def _canon(self, cuit):
        cuit = cuit.replace('-', '')
        return cuit[:-1], cuit[-1]

    def _calc_cd(self, cuit):
        # Calculation code based on:
        # http://es.wikipedia.org/wiki/C%C3%B3digo_%C3%9Anico_de_Identificaci%C3%B3n_Tributaria
        mults = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
        tmp = sum([m * int(cuit[idx]) for idx, m in enumerate(mults)])
        result = 11 - (tmp % 11)
        if result == 11:
            result = 0
        elif result == 10:
            result = 9
        return str(result)

    def _format(self, cuit, check_digit=None):
        if check_digit is None:
            check_digit = cuit[-1]
            cuit = cuit[:-1]
        return '%s-%s-%s' % (cuit[:2], cuit[2:], check_digit)


class ARCBUField(CharField):
    """
    This field validates a CBU (Clave Bancaria Uniforme).

    A CBU is a 22-digits long number. The first 8 digits denote bank and branch number,
    plus a verifying digit. The remaining 14 digits denote an account number, plus a verifying digit.

    More info:
    https://es.wikipedia.org/wiki/Clave_Bancaria_Uniforme

    .. versionadded:: 1.3
    .. versionchanged:: 3.0
    """

    default_error_messages = {
        'invalid': _('Enter a valid CBU in XXXXXXXXXXXXXXXXXXXXXX format.'),
        'max_length': _('CBU must be exactly 22 digits long.'),
        'min_length': _('CBU must be exactly 22 digits long.'),
        'checksum': _('Invalid CBU.'),
    }

    def clean(self, value):
        """Value must be a 22 digits long number."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        try:
            return cbu.validate(value)
        except InvalidLength:
            raise ValidationError(self.error_messages['max_length'], code='max_length')
        except InvalidChecksum:
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        except StdnumValidationError:
            raise ValidationError(self.error_messages['invalid'], code='invalid')
