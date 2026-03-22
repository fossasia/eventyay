"""China(mainland)-specific Form helpers."""

import re

from django.forms import ValidationError
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .cn_provinces import CN_PROVINCE_CHOICES

__all__ = (
    'CNProvinceSelect',
    'CNPostCodeField',
    'CNIDCardField',
)


ID_CARD_RE = r'^\d{15}(\d{2}[0-9xX])?$'
POST_CODE_RE = r'^\d{6}$'

# Valid location code used in id card checking algorithm
CN_LOCATION_CODES = (
    11,  # Beijing
    12,  # Tianjin
    13,  # Hebei
    14,  # Shanxi
    15,  # Nei Mongol
    21,  # Liaoning
    22,  # Jilin
    23,  # Heilongjiang
    31,  # Shanghai
    32,  # Jiangsu
    33,  # Zhejiang
    34,  # Anhui
    35,  # Fujian
    36,  # Jiangxi
    37,  # Shandong
    41,  # Henan
    42,  # Hubei
    43,  # Hunan
    44,  # Guangdong
    45,  # Guangxi
    46,  # Hainan
    50,  # Chongqing
    51,  # Sichuan
    52,  # Guizhou
    53,  # Yunnan
    54,  # Xizang
    61,  # Shaanxi
    62,  # Gansu
    63,  # Qinghai
    64,  # Ningxia
    65,  # Xinjiang
    71,  # Taiwan
    81,  # Hong Kong
    91,  # Macao
)


class CNProvinceSelect(Select):
    """A select widget providing the list of provinces and districts in People's Republic of China as choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=CN_PROVINCE_CHOICES)


class CNPostCodeField(RegexField):
    """
    A form field that validates input as postal codes in mainland China.

    Valid codes are in the format of XXXXXX where X is a digit.
    """

    default_error_messages = {
        'invalid': _('Enter a post code in the format XXXXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(POST_CODE_RE, **kwargs)


class CNIDCardField(CharField):
    """
    A form field that validates input as a Resident Identity Card (PRC) number.

    This field would check the following restrictions:
        * the length could only be 15 or 18;
        * if the length is 18, the last character can be x or X;
        * has a valid checksum (only for those with a length of 18);
        * has a valid date of birth;
        * has a valid province.

    The checksum algorithm is described in GB11643-1999.
    See: http://en.wikipedia.org/wiki/Resident_Identity_Card#Identity_card_number
    """

    default_error_messages = {
        'invalid': _('ID Card Number consists of 15 or 18 digits.'),
        'checksum': _('Invalid ID Card Number: Wrong checksum'),
        'birthday': _('Invalid ID Card Number: Wrong birthdate'),
        'location': _('Invalid ID Card Number: Wrong location code'),
    }

    def __init__(self, max_length=18, min_length=15, **kwargs):
        super().__init__(max_length=max_length, min_length=min_length, **kwargs)

    def clean(self, value):
        """Check whether the input is a valid ID Card Number."""
        # Check the length of the ID card number.
        value = super().clean(value)
        if value in self.empty_values:
            return value
        # Check whether this ID card number has valid format
        if not re.match(ID_CARD_RE, value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        # Check the birthday of the ID card number.
        if not self.has_valid_birthday(value):
            raise ValidationError(self.error_messages['birthday'], code='birthday' )
        # Check the location of the ID card number.
        if not self.has_valid_location(value):
            raise ValidationError(self.error_messages['location'], code='location')
        # Check the checksum of the ID card number.
        value = value.upper()
        if not self.has_valid_checksum(value):
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return '%s' % value

    def has_valid_birthday(self, value):
        """This method grabs the date of birth from the ID card number and test whether it is a valid date."""
        from datetime import datetime
        if len(value) == 15:
            # 1st generation ID card
            time_string = value[6:12]
            format_string = "%y%m%d"
        else:
            # 2nd generation ID card
            time_string = value[6:14]
            format_string = "%Y%m%d"
        try:
            datetime.strptime(time_string, format_string)
            return True
        except ValueError:
            # invalid date
            return False

    def has_valid_location(self, value):
        """This method checks if the first two digits in the ID Card are valid province code."""
        return int(value[:2]) in CN_LOCATION_CODES

    def has_valid_checksum(self, value):
        """This method checks if the last letter/digit is valid according to GB11643-1999."""
        # If the length of the number is not 18, then the number is a 1st
        # generation ID card number, and there is no checksum to be checked.
        if len(value) != 18:
            return True
        checksum_index = sum(
            map(lambda a, b: a * (ord(b) - ord('0')),
                (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2),
                value[:17],),
        ) % 11
        return '10X98765432'[checksum_index] == value[-1]
