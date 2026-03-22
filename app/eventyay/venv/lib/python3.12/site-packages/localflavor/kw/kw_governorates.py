from django.utils.translation import gettext_lazy as _

# List of governorates as defined by ISO_3166-2
# For reference; see https://en.wikipedia.org/wiki/ISO_3166-2:KW
# Note that these are governorates and not subdivisions

# These are the English names
GOVERNORATE_CHOICES = (
    ('AH', _('Ahmadi')),
    ('FA', _('Farwaniyah')),
    ('JA', _('Jahra')),
    ('KU', _('Capital')),
    ('HA', _('Hawalli')),
    ('MU', _('Mubarak Al Kabir')),
)
