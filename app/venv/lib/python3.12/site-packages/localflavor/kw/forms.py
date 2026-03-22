"""Kuwait-specific Form helpers."""
import re
import warnings

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from localflavor.deprecation import RemovedInLocalflavor60Warning

from .kw_areas import AREA_CHOICES
from .kw_governorates import GOVERNORATE_CHOICES
from .utils import is_valid_civil_id

id_re = re.compile(r'''^(?P<initial>\d)
                       (?P<yy>\d\d)
                       (?P<mm>\d\d)
                       (?P<dd>\d\d)
                       (?P<mid>\d{4})
                       (?P<checksum>\d)''', re.VERBOSE)


def is_valid_kw_civilid_checksum(value):
    """
    .. deprecated:: 5.0
       Use `localflavor.kw.utils.is_valid_civil_id()` instead.
    """
    warnings.warn(
        'is_valid_kw_civilid_checksum is deprecated in favor of localflavor.kw.utils.is_valid_civil_id().',
        RemovedInLocalflavor60Warning,
    )
    return is_valid_civil_id(value)


class KWCivilIDNumberField(RegexField):
    """
    Kuwaiti Civil ID numbers are 12 digits, second to seventh digits represents the person's birthdate.

    Checks the following rules to determine the validity of the number:
        * The number consist of 12 digits.
        * The first(century) digit should be 1, 2, or 3.
        * The birthdate of the person is a valid date.
        * The calculated checksum equals to the last digit of the Civil ID.
    """

    default_error_messages = {
        'invalid': _('Enter a valid Kuwaiti Civil ID number'),
    }

    def __init__(self, max_length=12, min_length=12, **kwargs):
        super().__init__(
            r'\d{12}', max_length=max_length, min_length=min_length,
            **kwargs
        )

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        if not is_valid_civil_id(value):
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        return value


class KWGovernorateSelect(Select):
    """
    A Select widget that uses a list of Kuwait governorates
    as its choices.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=GOVERNORATE_CHOICES)


class KWAreaSelect(Select):
    """
    A Select widget that uses a list of Kuwait areas
    as its choices.

    .. versionadded:: 1.6
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=AREA_CHOICES)
