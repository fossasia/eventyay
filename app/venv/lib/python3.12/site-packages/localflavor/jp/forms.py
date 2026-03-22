"""JP-specific Form helpers."""

from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .jp_prefectures import JP_PREFECTURE_CODES, JP_PREFECTURES


class JPPostalCodeField(RegexField):
    """
    A form field that validates its input is a Japanese postcode.

    Accepts 7 digits, with or without a hyphen.
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in the format XXXXXXX or XXX-XXXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^\d{3}-\d{4}$|^\d{7}$', **kwargs)

    def clean(self, value):
        """
        Validates the input and returns a string that contains only numbers.
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value
        return value.replace('-', '')


class JPPrefectureSelect(Select):
    """A Select widget that uses a list of Japanese prefectures as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=JP_PREFECTURES)


class JPPrefectureCodeSelect(Select):
    """
    A Select widget for Japanese prefecture codes.

    It uses a list of Japanese prefectures as its choices and the prefectures code as the post value.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=JP_PREFECTURE_CODES)
