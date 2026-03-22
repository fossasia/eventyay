from django.utils.translation import gettext_lazy as _

#: An alphabetical list of states for use as `choices` in a formfield.
# Codes taken from http://en.wikipedia.org/wiki/ISO_3166-2:PK
STATE_CHOICES = (
    ('PK-JK', _('Azad Jammu & Kashmir')),
    ('PK-BA', _('Balochistan')),
    ('PK-TA', _('Federally Administered Tribal Areas')),
    ('PK-GB', _('Gilgit-Baltistan')),
    ('PK-IS', _('Islamabad')),
    ('PK-KP', _('Khyber Pakhtunkhwa')),
    ('PK-PB', _('Punjab')),
    ('PK-SD', _('Sindh')),
)
