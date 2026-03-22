"""
New Zealand Provinces.

See "The Anniversary Day of the Province" at the source URL.

Source: http://www.dol.govt.nz/er/holidaysandleave/publicholidays/publicholidaydates/future-dates.asp

Note that provinces were abolished in 1876 and the names have very limited modern uses.

Source: http://en.wikipedia.org/wiki/Provinces_of_New_Zealand
"""

from django.utils.translation import gettext_lazy as _

#: A list of provinces (abolished in 1876, use regions instead)
PROVINCE_CHOICES = (
    ('Auckland', _('Auckland')),
    ('Taranaki', _('Taranaki')),
    ('Hawke\'s Bay', _('Hawke\'s Bay')),
    ('Wellington', _('Wellington')),
    ('Marlborough', _('Marlborough')),
    ('Nelson', _('Nelson')),
    ('Canterbury', _('Canterbury')),
    ('South Canterbury', _('South Canterbury')),
    ('Westland', _('Westland')),
    ('Otago', _('Otago')),
    ('Southland', _('Southland')),
    ('Chatham Islands', _('Chatham Islands')),
)
