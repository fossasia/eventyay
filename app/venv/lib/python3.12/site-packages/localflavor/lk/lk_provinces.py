"""
List of Provinces of Sri Lanka.

Source: https://en.wikipedia.org/wiki/Provinces_of_Sri_Lanka

Sri Lanka province list choices are in this format:

    ('name_of_province',_('Name of province')),

e.g.
    ('central', _('Central')),
"""

from django.utils.translation import gettext_lazy as _

PROVINCES = [
    ('central', _('Central')),
    ('eastern', _('Eastern')),
    ('north_central', _('North Central')),
    ('north_western', _('North Western')),
    ('northern', _('Northern')),
    ('sabaragamuwa', _('Sabaragamuwa')),
    ('southern', _('Southern')),
    ('uva', _('Uva')),
    ('western', _('Western')),
]
