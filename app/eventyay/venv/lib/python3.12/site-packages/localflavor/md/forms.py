from django import forms

from .choices import COMPANY_TYPES_CHOICES, REGION_CHOICES_2002_2015
from .validators import MDIDNOFieldValidator, MDLicensePlateValidator


class MDIDNOField(forms.CharField):
    """
    A form field for the Moldavian company identification number (IDNO).

    .. versionadded:: 2.1
    """

    default_validators = [MDIDNOFieldValidator()]

    def __init__(self, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(**kwargs)


class MDLicensePlateField(forms.CharField):
    """
    A form field for the Moldavian license plate number.

    .. versionadded:: 2.1
    """

    default_validators = [MDLicensePlateValidator()]

    def __init__(self, **kwargs):
        kwargs['max_length'] = 13
        super().__init__(**kwargs)


class MDCompanyTypesSelect(forms.Select):
    """
    A Select widget that uses a list of Moldavian company types as its choices.

    .. versionadded:: 2.1
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=COMPANY_TYPES_CHOICES)


class MDRegionSelect(forms.Select):
    """
    A Select widget that uses a list of Moldavian regions as its choices.

    .. versionadded:: 2.1
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES_2002_2015)
