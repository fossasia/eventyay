"""HU-specific Form helpers"""

from django.forms.fields import Select

from .hu_counties import HU_COUNTY_CHOICES


class HUCountySelect(Select):
    """
    A Select widget that uses a list of Hungarian Counties as its choices.

    .. versionadded:: 1.3
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=HU_COUNTY_CHOICES)
