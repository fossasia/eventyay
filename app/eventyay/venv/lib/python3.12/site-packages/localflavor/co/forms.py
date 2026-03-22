"""Colombian-specific form helpers."""

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .co_departments import DEPARTMENT_CHOICES


class CODepartmentSelect(Select):
    """A Select widget that uses a list of Colombian states as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=DEPARTMENT_CHOICES)


class CONITField(RegexField):
    """
    This field validates a NIT (NUmero de IdentificaciOn Tributaria). A
    NIT is of the form XXXXXXXXXX-V. The last digit is a check digit. This
    field can be used for people and companies.

    More info:
    http://es.wikipedia.org/wiki/N%C3%BAmero_de_Identificaci%C3%B3n_Tributaria
    """
    default_error_messages = {
        'invalid': _('Enter a valid NIT in XXXXXXXXXXX-Y or XXXXXXXXXXXY format.'),
        'checksum': _('Invalid NIT.'),
    }

    PRIME_PLACES = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]

    def __init__(self, **kwargs):
        super().__init__(r'^\d{5,12}-?\d$', **kwargs)

    def clean(self, value):
        """
        Value can be either a string in the format XXXXXXXXXX-Y or
        XXXXXXXXXXY.
        """
        value = super().clean(value)
        if value in self.empty_values:
            return value
        value, cd = self._canon(value)
        if self._calc_cd(value) != cd:
            raise ValidationError(self.error_messages['checksum'], code='checksum')
        return self._format(value, cd)

    def _canon(self, nit):
        nit = nit.replace('-', '')
        return nit[:-1], nit[-1]

    def _calc_cd(self, nit):
        # Calculation code based on:
        # http://es.wikipedia.org/wiki/N%C3%BAmero_de_Identificaci%C3%B3n_Tributaria
        tmp = sum([
            self.PRIME_PLACES[idx] * int(value)
            for idx, value in enumerate(reversed(nit))
        ]) % 11
        if tmp > 1:
            dv = 11 - tmp
        else:
            dv = 0
        return str(dv)

    def _format(self, nit, check_digit):
        return '{0}-{1}'.format(nit, check_digit)
