"""
New Zealand regions.

Source: http://en.wikipedia.org/wiki/Regions_of_New_Zealand#List_of_regions

"""

from django.utils.translation import gettext_lazy as _

#: A list of regions
REGION_CHOICES = (
    ('NZ-NTL', _('Northland')),
    ('NZ-AUK', _('Auckland')),
    ('NZ-WKO', _('Waikato')),
    ('NZ-BOP', _('Bay of Plenty')),
    ('NZ-GIS', _('Gisborne')),
    ('NZ-HKB', _('Hawke\'s Bay')),
    ('NZ-TKI', _('Taranaki')),
    ('NZ-MWT', _('Manawatu-Wanganui')),
    ('NZ-WGN', _('Wellington')),
    ('NZ-TAS', _('Tasman')),
    ('NZ-NSN', _('Nelson')),
    ('NZ-MBH', _('Marlborough')),
    ('NZ-WTC', _('West Coast')),
    ('NZ-CAN', _('Canterbury')),
    ('NZ-OTA', _('Otago')),
    ('NZ-STL', _('Southland')),
)
