"""IE-specific Form helpers."""

from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .ie_counties import IE_COUNTY_CHOICES


class IECountySelect(Select):
    """A Select widget that uses a list of Irish Counties as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=IE_COUNTY_CHOICES)


class EircodeField(RegexField):
    """
    A form field that validates its input is a valid Eircode (Irish postcode).

    The value is uppercased and has the internal space removed, if any.

    See page 12 for the validation syntax:
    https://www.eircode.ie/docs/default-source/Common/prepareyourbusinessforeircode-edition3published.pdf?sfvrsn=2

    .. versionadded:: 2.2
    """

    default_error_messages = {"invalid": _("Enter a valid Eircode.")}

    def __init__(self, **kwargs):
        kwargs.setdefault('strip', True)
        super().__init__("^(D6W|[AC-FHKNPRTV-Y][0-9]{2})([AC-FHKNPRTV-Y0-9]{4})$",
                         **kwargs)

    def to_python(self, value):
        # The Eircode should be stored as uppercase without spaces (see page 7):
        # https://www.eircode.ie/docs/default-source/Common/prepareyourbusinessforeircode-edition3published.pdf?sfvrsn=2
        value = super().to_python(value)
        if value in self.empty_values:
            return value
        return value.upper().replace(" ", "")

    def prepare_value(self, value):
        # Display the Eircode with a space.
        value = self.to_python(value)
        if value in self.empty_values:
            return value
        return '{} {}'.format(value[0:3], value[3:8])
