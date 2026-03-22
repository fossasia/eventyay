from django.core.validators import RegexValidator
from django.db.models import CharField
from django.utils.translation import gettext_lazy as _

from .ua_regions import UA_REGION_CHOICES


class UARegionField(CharField):
    """
    A model field which stores a Ukrainian region.

    This field is represented by forms as
    a :class:`~localflavor.ua.forms.UARegionSelect` field.

    .. versionadded:: 1.5
    """

    description = _('Ukrainian region')

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = UA_REGION_CHOICES
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class UAVatNumberField(CharField):
    """
    A model field which stores a Ukrainian analog of a VAT number.

    This field is represented by forms as
    a :class:`~localflavor.ua.forms.UAVatNumberField` field.

    .. versionadded:: 1.5
    """

    description = _('Ukrainian VAT number')
    validators = [RegexValidator(r'^\d{10}$', 'Enter a valid VAT number.')]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 10
        super().__init__(*args, **kwargs)


class UAPostalCodeField(CharField):
    """
    A model field which stores a Ukrainian postal code.

    This field is represented by forms as
    a :class:`~localflavor.ua.forms.UAPostalCodeField` field.

    .. versionadded:: 1.5
    """

    description = _('Ukrainian postal code')
    validators = [RegexValidator(r'^(?!00)\d{5}$', 'Enter a valid postal code.')]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)
