"""UY-specific form helpers."""

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .util import get_validation_digit


class UYDepartmentSelect(Select):
    """A Select widget that uses a list of Uruguayan departments as its choices."""

    def __init__(self, attrs=None):
        from .uy_departments import DEPARTMENT_CHOICES
        super().__init__(attrs, choices=DEPARTMENT_CHOICES)


class UYCIField(RegexField):
    """A field that validates Uruguayan 'Cedula de identidad' (CI) numbers."""

    default_error_messages = {
        'invalid': _("Enter a valid CI number in X.XXX.XXX-X,"
                     "XXXXXXX-X or XXXXXXXX format."),
        'invalid_validation_digit': _("Enter a valid CI number."),
    }

    def __init__(self, **kwargs):
        super().__init__(r'(?P<num>(\d{6,7}|(\d\.)?\d{3}\.\d{3}))-?(?P<val>\d)', **kwargs)

    def clean(self, value):
        """
        Validates format and validation digit.

        The official format is [X.]XXX.XXX-X but usually dots and/or slash are
        omitted so, when validating, those characters are ignored if found in
        the correct place. The three typically used formats are supported:
        [X]XXXXXXX, [X]XXXXXX-X and [X.]XXX.XXX-X.
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value
        match = self.regex.match(value)
        if not match:
            raise ValidationError(self.error_messages['invalid'], code='invalid')

        number = int(match.group('num').replace('.', ''))
        validation_digit = int(match.group('val'))

        if validation_digit != get_validation_digit(number):
            raise ValidationError(self.error_messages['invalid_validation_digit'], code='invalid_validation_digit')

        return value
