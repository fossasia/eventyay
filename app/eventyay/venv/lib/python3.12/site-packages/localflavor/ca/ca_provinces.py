from django.utils.translation import gettext_lazy as _

#: An alphabetical list of provinces and territories for use as `choices`
#: in a formfield. Source: http://www.canada.gc.ca/othergov/prov_e.html
PROVINCE_CHOICES = (
    ('AB', _('Alberta')),
    ('BC', _('British Columbia')),
    ('MB', _('Manitoba')),
    ('NB', _('New Brunswick')),
    ('NL', _('Newfoundland and Labrador')),
    ('NT', _('Northwest Territories')),
    ('NS', _('Nova Scotia')),
    ('NU', _('Nunavut')),
    ('ON', _('Ontario')),
    ('PE', _('Prince Edward Island')),
    ('QC', _('Quebec')),
    ('SK', _('Saskatchewan')),
    ('YT', _('Yukon'))
)

#: a mapping of province misspellings/abbreviations to normalized abbreviations
PROVINCES_NORMALIZED = {
    'ab': 'AB',
    'alberta': 'AB',
    'bc': 'BC',
    'b.c.': 'BC',
    'british columbia': 'BC',
    'mb': 'MB',
    'manitoba': 'MB',
    'nb': 'NB',
    'new brunswick': 'NB',
    'nf': 'NL',
    'nl': 'NL',
    'newfoundland': 'NL',
    'newfoundland and labrador': 'NL',
    'nt': 'NT',
    'northwest territories': 'NT',
    'ns': 'NS',
    'nova scotia': 'NS',
    'nu': 'NU',
    'nunavut': 'NU',
    'on': 'ON',
    'ontario': 'ON',
    'pe': 'PE',
    'pei': 'PE',
    'p.e.i.': 'PE',
    'prince edward island': 'PE',
    'pq': 'QC',
    'qc': 'QC',
    'quebec': 'QC',
    'sk': 'SK',
    'saskatchewan': 'SK',
    'yk': 'YT',
    'yt': 'YT',
    'yukon': 'YT',
    'yukon territory': 'YT',
}
