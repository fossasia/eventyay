"""PE-specific Form helpers."""

from django.forms import ValidationError
from django.forms.fields import CharField, Select
from django.utils.translation import gettext_lazy as _

from .pe_region import REGION_CHOICES


class PERegionSelect(Select):
    """A Select widget that uses a list of Peruvian Regions as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class PEDNIField(CharField):
    """A field that validates Documento Nacional de Identidad (DNI) numbers."""

    default_error_messages = {
        'invalid': _("This field requires only numbers."),
        'max_digits': _("This field requires 8 digits."),
    }

    def __init__(self, max_length=8, min_length=8, **kwargs):
        super().__init__(max_length=max_length, min_length=min_length, **kwargs)

    def clean(self, value):
        """Value must be a string in the XXXXXXXX formats."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not value.isdigit():
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if len(value) != 8:
            raise ValidationError(self.error_messages['max_digits'], code='max_digits')

        return value


class PERUCField(CharField):
    """
    This field validates a RUC (Registro Unico de Contribuyentes).

    A RUC is of the form XXXXXXXXXXX.
    """

    default_error_messages = {
        'invalid': _("This field requires only numbers."),
        'max_digits': _("This field requires 11 digits."),
    }

    def __init__(self, max_length=11, min_length=11, **kwargs):
        super().__init__(max_length=max_length, min_length=min_length, **kwargs)

    def clean(self, value):
        """Value must be an 11-digit number."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        if not value.isdigit():
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        if len(value) != 11:
            raise ValidationError(self.error_messages['max_digits'], code='max_digits')
        return value
