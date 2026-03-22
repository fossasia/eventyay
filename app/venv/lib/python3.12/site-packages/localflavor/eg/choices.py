from django.utils.translation import gettext_lazy as _

# List of governorates as defined by ISO_3166-2
# For reference; see https://en.wikipedia.org/wiki/ISO_3166-2:EG
# Note that these are governorates and not subdivisions

GOVERNORATE_CHOICES = (
    ('DK', _('Dakahlia')),
    ('BA', _('Red Sea')),
    ('BH', _('Beheira')),
    ('FYM', _('Faiyum')),
    ('GH', _('Gharbia')),
    ('ALX', _('Alexandria')),
    ('IS', _('Ismailia')),
    ('GZ', _('Giza')),
    ('MNF', _('Monufia')),
    ('MN', _('Minya')),
    ('C', _('Cairo')),
    ('KB', _('Qalyubia')),
    ('LX', _('Luxor')),
    ('WAD', _('New Valley')),
    ('SUZ', _('Suez')),
    ('SHR', _('Al Sharqia')),
    ('ASN', _('Aswan')),
    ('AST', _('Asyut')),
    ('BNS', _('Beni Suef')),
    ('PTS', _('Port Said')),
    ('DT', _('Damietta')),
    ('JS', _('South Sinai')),
    ('KFS', _('Kafr el-Sheikh')),
    ('MT', _('Matrouh')),
    ('KN', _('Qena')),
    ('SIN', _('North Sinai')),
    ('SHG', _('Sohag')),
)
