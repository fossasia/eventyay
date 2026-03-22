from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .forms import ESIdentityCardNumberField as ESIdentityCardNumberFormField
from .forms import ESPostalCodeField as ESPostalCodeFormField


class ESPostalCodeField(CharField):
    """
    A model field that stores the five numbers (XXXXX) of Spain Postal Codes

    Forms represent it as ``form.ESPostalCodeField``

    .. versionadded:: 2.2
    """

    description = _("Spain postal code (five numbers)")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': ESPostalCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class ESIdentityCardNumberField(CharField):
    """A model field that stores Spanish NIF/NIE/CIF in format ``XXXXXXXXX``

    Forms represent it as ``form.ESIdentityCardNumberField`` field.

    .. versionadded:: 2.2
    """

    description = _("Identification National Document")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 9
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value is not None:
            return value.upper().replace(' ', '').replace('-', '')
        return value

    def formfield(self, **kwargs):
        defaults = {'form_class': ESIdentityCardNumberFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
