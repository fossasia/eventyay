"""Sri Lanka specific Form helpers."""

from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .lk_provinces import PROVINCES
from .lk_districts import DISTRICTS


class LKPostalCodeFormField(RegexField):
    """
        A form field that accepts Sri Lanka postal code.
        Format : NNNNN

        Postal codes: https://en.wikipedia.org/wiki/Postal_codes_in_Sri_Lanka

        .. versionadded:: 5.0
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in format NNNNN'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^[0-9]{5}$', **kwargs)


class LKProvinceSelect(Select):
    """
        A Select widget with option to select a provinces from
        list of all provinces of Sri Lanka.

        .. versionadded:: 5.0
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCES)


class LKDistrictSelect(Select):
    """
    A Select widget with option to select a districts from
    list of all districts of Sri Lanka.

    .. versionadded:: 5.0
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=DISTRICTS)
