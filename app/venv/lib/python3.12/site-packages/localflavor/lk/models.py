"""Sri Lanka specific Model fields"""

import re

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from .forms import LKPostalCodeFormField
from .lk_districts import DISTRICTS
from .lk_provinces import PROVINCES


class LKPostalCodeValidator(RegexValidator):
    """
    A validator for Sri Lanka Postal Codes.
    """
    default_error_messages = {
        'invalid': _('Enter a postal code in format NNNNN'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(re.compile(r'^[0-9]{5}$'), *args, **kwargs)


class LKPostalCodeField(models.CharField):
    """
    A model field that accepts Sri Lanka postal codes.
    Format: NNNNN
    Source: https://en.wikipedia.org/wiki/Postal_codes_in_Sri_Lanka

    .. versionadded:: 5.0
    """
    description = _("Postal Code")

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)
        self.validators.append(LKPostalCodeValidator())

    def formfield(self, **kwargs):
        defaults = {'form_class': LKPostalCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)


class LKDistrictField(models.CharField):
    """
    A model field that provides an option to select
    a district from the list of all Sri Lanka districts.

    .. versionadded:: 5.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = DISTRICTS
        kwargs['max_length'] = 15
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs


class LKProvinceField(models.CharField):
    """
    A model field that provides an option to select
    a province from the list of all Sri Lanka provinces.

    .. versionadded:: 5.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = PROVINCES
        kwargs['max_length'] = 15
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs
