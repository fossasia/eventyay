from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .forms import MKIdentityCardNumberField as MKIdentityCardNumberFormField
from .forms import UMCNField as UMCNFormField
from .mk_choices import MK_MUNICIPALITIES


class MKIdentityCardNumberField(CharField):
    """
    A form field that validates input as a Macedonian identity card number.

    Both old and new identity card numbers are supported.
    """

    description = _("Macedonian identity card number")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 8
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': MKIdentityCardNumberFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class MKMunicipalityField(CharField):
    """
    A form field that validates input as a Macedonian identity card number.

    Both old and new identity card numbers are supported.
    """

    description = _("A Macedonian municipality (2 character code)")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = MK_MUNICIPALITIES
        kwargs['max_length'] = 2
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class UMCNField(CharField):
    """
    A form field that validates input as a unique master citizen number.

    The format of the unique master citizen number is not unique
    to Macedonia. For more information see:
    https://secure.wikimedia.org/wikipedia/en/wiki/Unique_Master_Citizen_Number

    A value will pass validation if it complies to the following rules:

    * Consists of exactly 13 digits
    * The first 7 digits represent a valid past date in the format DDMMYYY
    * The last digit of the UMCN passes a checksum test
    """

    description = _("Unique master citizen number (13 digits)")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {'form_class': UMCNFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)
