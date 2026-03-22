"""
List of Districts of Sri Lanka.

Source: https://en.wikipedia.org/wiki/Districts_of_Sri_Lanka

Sri Lanka districts list choices are in this format:

    ('name_of_districts',_('Name of districts')),

eg.
    ('name_of_district', _('Name of district')),
"""

from django.utils.translation import gettext_lazy as _

# list of districts in Central
CENTRAL_DISTRICTS = [
    ('kandy', _('Kandy')),
    ('matale', _('Matale')),
    ('nuwara_eliya', _('Nuwara Eliya')),
]

# list of districts in North Central
NORTH_CENTRAL_DISTRICTS = [
    ('anuradhapura', _('Anuradhapura')),
    ('polonnaruwa', _('Polonnaruwa')),
]

# list of districts in Northern
NORTHERN_DISTRICTS = [
    ('jaffna', _('Jaffna')),
    ('kilinochchi', _('Kilinochchi')),
    ('mannar', _('Mannar')),
    ('vavuniya', _('Vavuniya')),
    ('mullativu', _('Mullativu')),
    ('alambil', _('Alambil')),
]

# list of districts in Eastern
EASTERN_DISTRICTS = [
    ('ampara', _('Ampara')),
    ('batticaloa', _('Batticaloa')),
    ('trincomalee', _('Trincomalee')),
]

# list of districts in North Western
NORTH_WESTERN_DISTRICTS = [
    ('kurunagala', _('Kurunagala')),
    ('puttalam', _('Puttalam')),
]

# list of districts in Southern
SOUTHERN_DISTRICTS = [
    ('galle', _('Galle')),
    ('hambanthota', _('Hambanthota')),
    ('mathara', _('Mathara')),
]

# list of districts in Uva
UVA_DISTRICTS = [
    ('badulla', _('Badulla')),
    ('monaragala', _('Monaragala')),
]

# list of districts in Sabaragamuwa
SABARAGAMUWA_DISTRICTS = [
    ('kegalle', _('Kegalle')),
    ('rathnapura', _('Rathnapura')),
]

# list of districts in Western
WESTERN_DISTRICTS = [
    ('colombo', _('Colombo')),
    ('gampaha', _('Gampaha')),
    ('kaluthara', _('Kaluthara')),
]

# Combining all the district lists from different provinces into a single list
DISTRICTS =  CENTRAL_DISTRICTS + NORTH_CENTRAL_DISTRICTS + NORTHERN_DISTRICTS + EASTERN_DISTRICTS + NORTH_WESTERN_DISTRICTS + SOUTHERN_DISTRICTS + UVA_DISTRICTS + SABARAGAMUWA_DISTRICTS + WESTERN_DISTRICTS

# Alphabetically sorting the list of all districts based on their names (first element of each tuple)
DISTRICTS.sort(key=lambda district: district[0])
