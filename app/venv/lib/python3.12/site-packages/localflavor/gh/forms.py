"""Ghana specific form helpers."""

from django.forms.fields import Select

from .gh_regions import REGIONS


class GHRegionSelect(Select):
    """
    A Select widget with option to select a region from
    list of all regions of Ghana.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGIONS)
