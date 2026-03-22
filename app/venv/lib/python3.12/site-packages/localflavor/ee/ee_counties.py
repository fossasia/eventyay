from django.utils.translation import gettext_lazy as _

#: A list of Estonian counties as `choices` in a formfield.
#: Identifiers based on ISO 3166-2:EE. https://en.wikipedia.org/wiki/ISO_3166-2:EE
COUNTY_CHOICES = (
    ('37', _('Harju County')),
    ('39', _('Hiiu County')),
    ('44', _('Ida-Viru County')),
    ('49', _('Jõgeva County')),
    ('51', _('Järva County')),
    ('57', _('Lääne County')),
    ('59', _('Lääne-Viru County')),
    ('65', _('Põlva County')),
    ('67', _('Pärnu County')),
    ('70', _('Rapla County')),
    ('74', _('Saare County')),
    ('78', _('Tartu County')),
    ('82', _('Valga County')),
    ('84', _('Viljandi County')),
    ('86', _('Võru County')),
)
