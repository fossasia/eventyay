"""Nepal specific Model fields"""

import re

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from .forms import NPPostalCodeFormField
from .np_districts import DISTRICTS
from .np_provinces import PROVINCES
from .np_zones import ZONES


class NPPostalCodeValidator(RegexValidator):
    """
    A validator for Nepali Postal Codes.
    """
    default_error_messages = {
        'invalid': _('Enter a postal code in format XXXXX'),
    }

    def __init__(self,*args, **kwargs):
        super().__init__(re.compile(r'^\d{5}$'), *args,**kwargs)

class NPPostalCodeField(models.CharField):
    """
        A model field that accepts Nepali postal codes.
        Format: XXXXX
        Source: https://en.wikipedia.org/wiki/List_of_postal_codes_in_Nepal
        .. versionadded:: 4.0
    """
    description = _("Postal Code")
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)
        self.validators.append(NPPostalCodeValidator())

    def formfield(self, **kwargs):
        defaults = {'form_class': NPPostalCodeFormField}
        defaults.update(kwargs)
        return super().formfield(**defaults)

class NPDistrictField(models.CharField):
    """
        A model field that provides an option to select 
        a district from the list of all Nepali districts.
        .. versionadded:: 4.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = DISTRICTS
        kwargs['max_length'] = 15
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs
        
class NPZoneField(models.CharField):
    """
        A model field that provides an option to select 
        a zone from the list of all Nepali zones.
        .. versionadded:: 4.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = ZONES
        kwargs['max_length'] = 11
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs

class NPProvinceField(models.CharField):
    """
        A model field that provides an option to select 
        a province from the list of all Nepali provinces.
        .. versionadded:: 4.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = PROVINCES
        kwargs['max_length'] = 12
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs
