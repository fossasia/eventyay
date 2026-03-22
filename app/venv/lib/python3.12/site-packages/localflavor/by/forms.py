from django import forms
from django.utils.translation import gettext_lazy as _

from .by_regions import BY_REGIONS_CHOICES


class BaseKwargsUpdatedField:
    """
    Abstract base class made to conform the DRY principle.

    The initial_options is overridden by the dict in the subclasses and then
    automatically passed to kwargs in the FormField.__init__() method.
    """

    initial_options = None

    def __init__(self, *args, **kwargs):
        kwargs.update(self.initial_options)
        super().__init__(*args, **kwargs)


class UpperValueMixin:
    """
    Mixin made to conform the DRY principle.

    Overrides the to_python methods to return the value.upper()
    """

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return value.upper()


class BYRegionSelect(forms.Select):
    """
    A Select widget that uses a list of Belarusian regions as its choices.

    .. versionadded:: 4.0
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=BY_REGIONS_CHOICES)


class BYPassNumberField(BaseKwargsUpdatedField, UpperValueMixin, forms.RegexField):
    """
    A form field that validates its input is a pass number in a right format.

    Apart from that, it tries to convert all characters to uppercase as
    the format of belarussian pass number needs that to be right.

    The valid input format is: XX1234567.

    .. versionadded:: 4.0
    """

    initial_options = {
        'regex': r'^[A-Z]{2}\d{7}$',
        'error_messages': {
            'invalid': _('Passport number format is: XX1234567')
        },
    }


class BYPassIdNumberField(BaseKwargsUpdatedField, UpperValueMixin, forms.RegexField):
    """
    A form field that validates its input is a ID number in a right format.

    Apart from that, it tries to convert all characters of the input
    to uppercase as the format of belarussian pass id needs those
    to be valid.

    The valid input format is: 1234567X123XX1.

    .. versionadded:: 4.0
    """

    initial_options = {
        'regex': r'^\d{7}[A-Z]\d{3}[A-Z]{2}\d$',
        'error_messages': {
            'invalid': _('ID format is: 1234567X123XX1')
        },
    }


class BYPostalCodeField(BaseKwargsUpdatedField, forms.RegexField):
    """
    A form field that validates its input is a valid Postal code (6 digits).

    .. versionadded:: 4.0
    """

    initial_options = {
        'regex': r'^\d{6}$',
        'error_messages': {
            'invalid': _('Postal code format is: 123456')
        },
    }
