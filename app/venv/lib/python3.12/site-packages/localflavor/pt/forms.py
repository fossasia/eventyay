"""
django_localflavot_pt.forms
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contains PT-specific Django form helpers.
"""

from re import compile as regex_compile

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .pt_regions import REGION_CHOICES

CITIZEN_CARD_NUMBER_REGEX = regex_compile(r'^(\d{8})-?(\d[A-Z0-9]{2}\d)$')
SOCIAL_SECURITY_NUMBER_MULTIPLIERS = [29, 23, 19, 17, 13, 11, 7, 5, 3, 2]
SOCIAL_SECURITY_NUMBER_REGEX = regex_compile(r'^[12]\d{10}$')
ZIP_CODE_REGEX = regex_compile(r'^[1-9]\d{3}-\d{3}$')


class PTCitizenCardNumberField(CharField):
    """
    A field which validates Portuguese Citizen Card numbers (locally CC - 'Cartão do Cidadão').

    - Citizen Card numbers have the format XXXXXXXXXYYX or XXXXXXXX-XYYX
        (where X is a digit and Y is an alphanumeric character).
    - Citizen Card numbers validate as per http://bit.ly/RP0BzW.
    - The input string may or may not have an hyphen separating the identity number from the document's check-digits.
    - This field does NOT validate old ID card numbers (locally BI - 'Bilhete de Identidade').
    """

    default_error_messages = {
        'badchecksum': _('The specified value is not a valid Citizen Card number.'),
        'invalid': _('Citizen Card numbers have the format XXXXXXXXXYYX or XXXXXXXX-XYYX '
                     '(where X is a digit and Y is an alphanumeric character).'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = CITIZEN_CARD_NUMBER_REGEX.match(value)

        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        number, checkdigits = match.groups()

        encoded = number + checkdigits
        decoded = [int(digit, 36) for digit in encoded]

        checksum = sum([PTCitizenCardNumberField.compute(index, decoded_value)
                        for index, decoded_value in enumerate(decoded)])

        if not checksum % 10 == 0:
            raise ValidationError(self.error_messages['badchecksum'], code='badchecksum')

        return '{0}-{1}'.format(number, checkdigits)

    @staticmethod
    def compute(index, value):
        if index % 2:
            return value
        else:
            value *= 2
            return value if value < 10 else value - 9


class PTRegionSelect(Select):
    """
    A select widget which uses a list of Portuguese regions as its choices.

    - Regions correspond to the Portuguese 'distritos' and 'regiões autónomas' as per ISO3166:2-PT.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class PTSocialSecurityNumberField(CharField):
    """
    A field which validates Portuguese Social Security numbers.

    (locally NISS - 'Número de Identificação na Segurança Social').
    - Social Security numbers must be in the format XYYYYYYYYYY (where X is either 1 or 2 and Y is any other digit).
    """

    default_error_messages = {
        'badchecksum': _('The specified number is not a valid Social Security number.'),
        'invalid': _('Social Security numbers must be in the format XYYYYYYYYYY '
                     '(where X is either 1 or 2 and Y is any other digit).'),
    }

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        match = SOCIAL_SECURITY_NUMBER_REGEX.search(value)

        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        digits = [int(digit) for digit in value]

        factors = list(zip(digits, SOCIAL_SECURITY_NUMBER_MULTIPLIERS))
        dotproduct = sum(p * q for p, q in factors)

        checksum = 9 - dotproduct % 10
        checkdigit = int(value[-1])

        if not checksum == checkdigit:
            raise ValidationError(self.error_messages['badchecksum'], code='badchecksum')

        return int(value)


class PTZipCodeField(RegexField):
    """
    A field which validates Portuguese zip codes.

    NOTE
    - Zip codes have the format XYYY-YYY (where X is a digit between 1 and 9 and Y is any other digit).
    """

    default_error_messages = {
        'invalid': _('Zip codes must be in the format XYYY-YYY'
                     ' (where X is a digit between 1 and 9 and Y is any other digit).'),
    }

    def __init__(self, **kwargs):
        super().__init__(ZIP_CODE_REGEX, **kwargs)
