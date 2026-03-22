from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .forms import CASocialInsuranceNumberField as CASocialInsuranceNumberFormField
from .forms import CAPostalCodeField as CAPostalCodeFormField
from .ca_provinces import PROVINCE_CHOICES


class CAProvinceField(CharField):
    """
    A model field that stores the two-letter Canadian province abbreviation in the database.

    Forms represent it as a ``forms.CAProvinceField`` field.

    .. versionadded:: 4.0
    """

    description = _("Canadian Province (two uppercase letters)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = PROVINCE_CHOICES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class CAPostalCodeField(CharField):
    """
    A model field that stores the Canadian Postal code in the database.

    Forms represent it as a :class:`~localflavor.ca.forms.CAPostalCodeField` field.

    .. versionadded:: 4.0
    """

    description = _("Canadian Postal Code")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 7
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': CAPostalCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class CASocialInsuranceNumberField(CharField):
    """
    A model field that stores a Canadian Social Insurance Number (SIN) in the format ``XXX-XXX-XXX``.

    Forms represent it as ``forms.CASocialInsuranceNumberField`` field.

    .. versionadded:: 4.0
    """

    description = _("Canadian Social Insurance Number")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': CASocialInsuranceNumberFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
