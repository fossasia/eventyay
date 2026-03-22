"""MA-specific Form helpers"""
from django.forms.fields import CharField, RegexField, Select
from django.utils.translation import gettext_lazy as _

from .ma_provinces import PROVINCE_CHOICES_PER_REGION
from .ma_regions import REGION_CHOICES


class MAPostalCodeField(RegexField):
    """
    Validate local Moroccan postal code.

    The correct format is 'XXXXX' as defined in http://codepostal.ma/code_postal.aspx .

    .. versionadded:: 1.4
    """

    default_error_messages = {
        'invalid': _('Enter a postal code in the format XXXXX.'),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Postal code'))
        kwargs['max_length'] = 5
        kwargs['min_length'] = 5
        super().__init__(r'^\d{5}$', **kwargs)


class MAProvinceSelect(Select):
    """A Select widget that uses a list of MA provinces as its choices."""

    def __init__(self, attrs=None):
        choices = [
            (province[0], '%s - %s' % (province[0], province[1]))
            for province in PROVINCE_CHOICES_PER_REGION
        ]
        super().__init__(attrs, choices=choices)


class MARegionSelect(Select):
    """A Select widget that uses a list of MA regions as its choices."""

    def __init__(self, attrs=None):
        choices = [
            (region[0], '%s - %s' % (region[0], region[1]))
            for region in REGION_CHOICES
        ]
        super().__init__(attrs, choices=choices)


class MAProvinceField(CharField):
    """
    A Select Field that uses a MAProvinceSelect widget.

    .. versionadded:: 1.4
    """

    widget = MAProvinceSelect

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Select Province'))
        super().__init__(**kwargs)


class MARegionField(CharField):
    """
    A Select Field that uses a MARegionSelect widget.

    .. versionadded:: 1.4
    """

    widget = MARegionSelect

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('Select Region'))
        super().__init__(**kwargs)


class MACinNumberField(RegexField):
    """
        CIN number: (Numéro de la Carte D'Identité Nationale) The CIN represents the ID of a Moroccan citizen.

         - It is an 8-max-length string that starts with one or two Latin letters followed by digits,
           with the first digit not being zero.

         - as implemented in the official government site "https://www.cnie.ma/"
        .. versionadded:: 4.1
    """

    default_error_messages = {
        'invalid': _('Enter a valid Moroccan CIN number.'),
    }
    cin_pattern = r'^[A-Za-z]{1,2}[1-9][0-9]{0,6}$'

    def __init__(self, **kwargs):
        kwargs.setdefault('label', _('CIN Number'))
        kwargs['max_length'] = 8
        kwargs['min_length'] = 2
        super().__init__(self.cin_pattern, **kwargs)
