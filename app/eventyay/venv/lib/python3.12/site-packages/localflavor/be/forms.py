"""Belgium-specific Form helpers."""

from django.forms.fields import RegexField, Select
from django.utils.translation import gettext_lazy as _

from .be_provinces import PROVINCE_CHOICES
from .be_regions import REGION_CHOICES


class BEPostalCodeField(RegexField):
    """
    A form field that validates its input as a belgium postal code.

    Belgium postal code is a 4 digits string. The first digit indicates
    the province (except for the 3ddd numbers that are shared by the
    eastern part of Flemish Brabant and Limburg and the and 1ddd that
    are shared by the Brussels Capital Region, the western part of
    Flemish Brabant and Walloon Brabant)
    """

    default_error_messages = {
        'invalid': _(
            'Enter a valid postal code in the range and format 1XXX - 9XXX.'),
    }

    def __init__(self, **kwargs):
        super().__init__(r'^[1-9]\d{3}$', **kwargs)


class BERegionSelect(Select):
    """A Select widget that uses a list of belgium regions as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=REGION_CHOICES)


class BEProvinceSelect(Select):
    """A Select widget that uses a list of belgium provinces as its choices."""

    def __init__(self, attrs=None):
        super().__init__(attrs, choices=PROVINCE_CHOICES)
