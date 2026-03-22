from django.utils.translation import gettext_lazy as _

#: A list of Venezuelan regions for use as `choices` in a formfield.
#: Data based from http://en.wikipedia.org/wiki/Regions_of_Venezuela
REGION_CHOICES = (
    ('501', _('Región Capital')),
    ('502', _('Región Central')),
    ('503', _('Región de los Llanos')),
    ('504', _('Región Centro Occidental')),
    ('505', _('Región Zuliana')),
    ('506', _('Región de los Andes')),
    ('507', _('Región Nor-Oriental')),
    ('508', _('Región Insular')),
    ('509', _('Región Guayana')),
    ('510', _('Región Sur Occidental')),
)
