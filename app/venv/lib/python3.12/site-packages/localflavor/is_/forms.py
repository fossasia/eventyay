"""Iceland specific form helpers."""
from django.forms import ValidationError
from django.forms.fields import RegexField
from django.forms.widgets import Select
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from .is_postalcodes import IS_POSTALCODES


class ISIdNumberField(RegexField):
    """
    Icelandic identification number (kennitala).

    This is a number every citizen of Iceland has.
    """

    default_error_messages = {
        'invalid': _('Enter a valid Icelandic identification number. The format is XXXXXX-XXXX.'),
        'checksum': _('The Icelandic identification number is not valid.'),
    }

    def __init__(self, max_length=11, min_length=10, **kwargs):
        super().__init__(
            r'^\d{6}(-| )?\d{4}$', max_length=max_length, min_length=min_length,
            **kwargs
        )

    def clean(self, value):
        value = super().clean(value)

        if value in self.empty_values:
            return value

        value = self._canonify(value)
        if self._validate(value):
            return self._format(value)
        else:
            raise ValidationError(self.error_messages['checksum'], code='checksum')

    def _canonify(self, value):
        """Returns the value as only digits."""
        return value.replace('-', '').replace(' ', '')

    def _validate(self, value):
        """
        Takes in the value in canonical form and checks the verifier digit.

        The method is modulo 11.
        """
        check = [3, 2, 7, 6, 5, 4, 3, 2, 1, 0]
        return sum([int(value[i]) * check[i] for i in range(10)]) % 11 == 0

    def _format(self, value):
        """Takes in the value in canonical form and returns it in the common display format."""
        return force_str(value[:6] + '-' + value[6:])


class ISPostalCodeSelect(Select):
    """A Select widget that uses a list of Icelandic postal codes as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=IS_POSTALCODES)
