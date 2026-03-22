"""
List of Provinces of Ghana.
Source: https://www.ghanamissionun.org/map-regions-in-ghana/
Ghana regions list choices are in this format:
    ('name_of_region',_('Name of region')),
eg.
    ('ahafo', _('Ahafo')),
"""

from django.utils.translation import gettext_lazy as _

REGIONS = [
    ('ahafo', _('Ahafo')),
    ('ashanti', _('Ashanti')),
    ('bono_east', _('Bono East')),
    ('brong_ahafo', _('Brong Ahafo')),
    ('central', _('Central')),
    ('eastern', _('Eastern')),
    ('greater_accra', _('Greater Accra')),
    ('north_east', _('North East')),
    ('northern', _('Northern')),
    ('oti', _('Oti')),
    ('savannah', _('Savannah')),
    ('upper_east', _('Upper East')),
    ('upper_west', _('Upper West')),
    ('western', _('Western')),
    ('western_north', _('Western North')),
    ('volta', _('Volta')),
]