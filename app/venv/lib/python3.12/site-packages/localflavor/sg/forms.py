"""Singapore-specific Form helpers."""

import re

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

NRIC_FIN_RE = re.compile(r'^[SFTG](\d{7})[A-Z]$')
NRIC_FIN_DIGIT_WEIGHT = [2, 7, 6, 5, 4, 3, 2]
NRIC_FIN_CHECKSUM_ST = ['J', 'Z', 'I', 'H', 'G', 'F', 'E', 'D', 'C', 'B', 'A']
NRIC_FIN_CHECKSUM_FG = ['X', 'W', 'U', 'T', 'R', 'Q', 'P', 'N', 'M', 'L', 'K']


class SGPostCodeField(RegexField):
    """
    Singapore post code field.

    Assumed to be 6 digits.
    """

    default_error_messages = {
        'invalid': _('Enter a 6-digit postal code.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{6}$', **kwargs)


class SGNRICFINField(CharField):
    """
    A form field that validates input as a Singapore National Registration.

    Identity Card (NRIC) or Foreign Identification Number (FIN)

    Based on http://en.wikipedia.org/wiki/National_Registration_Identity_Card
    Checksum algorithm:
    1) Take for example I want to test the NRIC number S1234567.
    Multiply each digit by corresponding weight in this list [2,7,6,5,4,3,2]
    and add them together. So 1x2 + 2x7 + 3x6 + 4x5 + 5x4 + 6x3 + 7x2 = 106.
    2) If the first letter of the NRIC starts with T or G, add 4 to the total.
    3) Then you divide the number by 11 and get the remainder. 106/11=9r7
    4) You can get the alphabet depending on the IC type (the first letter in
    the IC) using the code below:
        S or T: 0=J, 1=Z, 2=I, 3=H, 4=G, 5=F, 6=E, 7=D, 8=C, 9=B, 10=A
        F or G: 0=X, 1=W, 2=U, 3=T, 4=R, 5=Q, 6=P, 7=N, 8=M, 9=L, 10=K
    """

    default_error_messages = {
        'invalid': _('Invalid NRIC/FIN.')
    }

    def clean(self, value):
        """
        Validate NRIC/FIN.

        Strips whitespace.
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value = re.sub(r'(\s+)', '', force_str(value.upper()))
        match = NRIC_FIN_RE.search(value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        value = match.group()
        digit_list = list(value[1:-1])
        products_sum = sum([int(x) * y for x, y in zip(digit_list,
                                                       NRIC_FIN_DIGIT_WEIGHT)])
        if value[0] in ['T', 'G']:
            products_sum += 4
        products_sum_remainder = products_sum % 11
        checksum_list = NRIC_FIN_CHECKSUM_ST if value[0] in ['S', 'T'] \
            else NRIC_FIN_CHECKSUM_FG
        checksum = checksum_list[products_sum_remainder]
        if checksum == value[len(value) - 1]:
            return value

        raise ValidationError(self.error_messages['invalid'], code='invalid')
