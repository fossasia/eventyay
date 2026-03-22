"""Australian-specific Form helpers."""

from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .au_states import STATE_CHOICES
from .validators import AUBusinessNumberFieldValidator, AUCompanyNumberFieldValidator, AUTaxFileNumberFieldValidator


class AUPostCodeField(RegexField):
    """
    Australian post code field.

    Assumed to be 4 digits.
    Northern Territory 3-digit postcodes should have leading zero.
    """

    default_error_messages = {
        'invalid': _('Enter a 4 digit postcode.'),
    }

    def __init__(self, max_length=4, **kwargs):
        super().__init__(r'^\d{4}$', max_length=max_length, **kwargs)


class AUStateSelect(Select):
    """A Select widget that uses a list of Australian states/territories as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)


class AUBusinessNumberField(CharField):
    """
    A form field that validates input as an Australian Business Number (ABN).

    .. versionadded:: 1.3
    .. versionchanged:: 1.4
    """

    default_validators = [AUBusinessNumberFieldValidator()]

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return value.upper().replace(' ', '')

    def prepare_value(self, value):
        """Format the value for display."""
        if value is None:
            return value

        spaceless = ''.join(value.split())
        return '{} {} {} {}'.format(spaceless[:2], spaceless[2:5], spaceless[5:8], spaceless[8:])


class AUCompanyNumberField(CharField):
    """
    A form field that validates input as an Australian Company Number (ACN).

    .. versionadded:: 1.5
    """

    default_validators = [AUCompanyNumberFieldValidator()]

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return value.upper().replace(' ', '')

    def prepare_value(self, value):
        """Format the value for display."""
        if value is None:
            return value

        spaceless = ''.join(value.split())
        return '{} {} {}'.format(spaceless[:3], spaceless[3:6], spaceless[6:])


class AUTaxFileNumberField(CharField):
    """
    A form field that validates input as an Australian Tax File Number (TFN).

    .. versionadded:: 1.4
    """

    default_validators = [AUTaxFileNumberFieldValidator()]

    def prepare_value(self, value):
        """Format the value for display."""
        if value is None:
            return value

        spaceless = ''.join(value.split())
        return '{} {} {}'.format(spaceless[:3], spaceless[3:6], spaceless[6:])
