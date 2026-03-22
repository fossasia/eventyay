"""Chile specific form helpers."""

from django.forms import ValidationError
from django.forms.fields import RegexField, Select
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from .cl_regions import REGION_CHOICES


class CLRegionSelect(Select):
    """A Select widget that uses a list of Chilean Regions (Regiones) as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class CLRutField(RegexField):
    """
    Chilean "Rol Unico Tributario" (RUT) field.

    This is the Chilean national identification number.

    Samples for testing are available from
    https://palena.sii.cl/cvc/dte/ee_empresas_emisoras.html
    """

    default_error_messages = {
        'invalid': _('Enter a valid Chilean RUT.'),
        'strict': _('Enter a valid Chilean RUT. The format is XX.XXX.XXX-X.'),
        'checksum': _('The Chilean RUT is not valid.'),
    }

    def __init__(self, **kwargs):
        if 'strict' in kwargs:
            del kwargs['strict']
            super().__init__(r'^(\d{1,2}\.)?\d{3}\.\d{3}-[\dkK]$',
                             error_messages={'invalid': self.default_error_messages['strict']},
                             **kwargs)
        else:
            # In non-strict mode, accept RUTs that validate but do not exist in
            # the real world.
            super().__init__(r'^[\d\.]{1,11}-?[\dkK]$', **kwargs)

    def clean(self, value):
        """Check and clean the Chilean RUT."""
        value = super().clean(value)
        if value in self.empty_values:
            return value
        rut, verificador = self._canonify(value)
        if self._algorithm(rut) == verificador:
            return self._format(rut, verificador)
        else:
            raise ValidationError(self.error_messages['checksum'], code='checksum')

    def _algorithm(self, rut):
        """Takes RUT in pure canonical form, calculates the verifier digit."""
        suma = 0
        multi = 2
        for r in rut[::-1]:
            suma += int(r) * multi
            multi += 1
            if multi == 8:
                multi = 2
        return '0123456789K0'[11 - suma % 11]

    def _canonify(self, rut):
        """Turns the RUT into one normalized format. Returns a (rut, verifier) tuple."""
        rut = force_str(rut).replace(' ', '').replace('.', '').replace('-', '')
        return rut[:-1], rut[-1].upper()

    def _format(self, code, verifier=None):
        """
        Formats the RUT from canonical form to the common string representation.

        If verifier=None, then the last digit in 'code' is the verifier.
        """
        if verifier is None:
            verifier = code[-1]
            code = code[:-1]
        while len(code) > 3 and '.' not in code[:3]:
            pos = code.find('.')
            if pos == -1:
                new_dot = -3
            else:
                new_dot = pos - 3
            code = code[:new_dot] + '.' + code[new_dot:]
        return '%s-%s' % (code, verifier)
