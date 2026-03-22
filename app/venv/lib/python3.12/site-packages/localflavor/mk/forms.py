import datetime

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .mk_choices import MK_MUNICIPALITIES


class MKIdentityCardNumberField(RegexField):
    """
    A Macedonian ID card number.

    Accepts both old and new format.
    """

    default_error_messages = {
        'invalid': _('Identity card numbers must contain'
                     ' either 4 to 7 digits or an uppercase letter and 7 digits.'),
    }

    def __init__(self, **kwargs):
        kwargs['min_length'] = None
        kwargs['max_length'] = 8
        regex = r'(^[A-Z]{1}\d{7}$)|(^\d{4,7}$)'
        super().__init__(regex, **kwargs)


class MKMunicipalitySelect(Select):
    """
    A form ``Select`` widget that uses a list of Macedonian municipalities as choices.

    The label is the name of the municipality and the value is a 2 character code for the municipality.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=MK_MUNICIPALITIES)


class UMCNField(RegexField):
    """
    A form field that validates input as a unique master citizen number.

    The format of the unique master citizen number has been kept the same from
    Yugoslavia. It is still in use in other countries as well, it is not applicable
    solely in Macedonia. For more information see:
    https://secure.wikimedia.org/wikipedia/en/wiki/Unique_Master_Citizen_Number

    A value will pass validation if it complies to the following rules:

    * Consists of exactly 13 digits
    * The first 7 digits represent a valid past date in the format DDMMYYY
    * The last digit of the UMCN passes a checksum test
    """

    default_error_messages = {
        'invalid': _('This field should contain exactly 13 digits.'),
        'date': _('The first 7 digits of the UMCN must represent a valid past date.'),
        'checksum': _('The UMCN is not valid.'),
    }

    def __init__(self, **kwargs):
        kwargs['min_length'] = None
        kwargs['max_length'] = 13
        super().__init__(r'^\d{13}$', **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        if not self._validate_date_part(value):
            raise ValidationError(self.error_messages['date'], code='date')
        if self._validate_checksum(value):
            return value
        else:
            raise ValidationError(self.error_messages['checksum'], code='checksum')

    def _validate_checksum(self, value):
        a, b, c, d, e, f, g, h, i, j, k, l, checksum = [int(digit) for digit in value]
        m = 11 - ((7 * (a + g) + 6 * (b + h) + 5 * (c + i) + 4 * (d + j) + 3 * (e + k) + 2 * (f + l)) % 11)
        if 1 <= m <= 9 and checksum == m:
            return True
        elif m == 11 and checksum == 0:
            return True
        else:
            return False

    def _validate_date_part(self, value):
        daypart, monthpart, yearpart = int(value[:2]), int(value[2:4]), int(value[4:7])
        if yearpart >= 800:
            yearpart += 1000
        else:
            yearpart += 2000
        try:
            date = datetime.datetime(year=yearpart, month=monthpart, day=daypart).date()
        except ValueError:
            return False
        if date >= datetime.datetime.now().date():
            return False
        return True
