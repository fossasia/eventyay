from django.db.models import CharField
from django.utils.translation import gettext as _

from .choices import COMPANY_TYPES_CHOICES
from .validators import MDIDNOFieldValidator, MDLicensePlateValidator


class MDIDNOField(CharField):
    """
    A model field for the Moldavian company identification number (IDNO).

    .. versionadded:: 2.1
    """
    description = _("Moldavian identity number")
    validators = [MDIDNOFieldValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(*args, **kwargs)


class MDLicensePlateField(CharField):
    """
    A model field for the Moldavian license plate number.

    .. versionadded:: 2.1
    """

    description = _("Moldavian license plate number")
    validators = [MDLicensePlateValidator()]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 9
        super().__init__(*args, **kwargs)


class MDCompanyTypeField(CharField):
    """
    A model field for the Moldavian company type abbreviation.

    .. versionadded:: 2.1
    """

    description = _("Moldavian company types")

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = COMPANY_TYPES_CHOICES
        kwargs['max_length'] = 5
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs
