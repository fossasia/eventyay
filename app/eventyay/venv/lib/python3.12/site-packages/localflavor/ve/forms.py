"""
Ve-specific Form helpers.
"""

from django.forms.fields import Select

from .ve_region import REGION_CHOICES
from .ve_states import STATE_CHOICES


class VERegionSelect(Select):
    """
    A Select widget that uses a list of Venezuelan regions as its choices.
    """
    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class VEStateSelect(Select):
    """
    A Select widget that uses a list of Venezuelan states as its choices.
    """
    def __init__(self, attrs=None):
        super().__init__(attrs, choices=STATE_CHOICES)
