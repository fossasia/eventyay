from django.utils.translation import gettext_lazy as _

#: An alphabetical list of regions for use as `choices` in a formfield.
#: http://www.pncl.gov.ma/fr/Pages/decoupage.aspx
REGION_CHOICES = (
    ('01', _('Tanger-Tétouan-Al Hoceïma')),
    ('02', _('L’Oriental')),
    ('03', _('Fès-Meknès')),
    ('04', _('Rabat-Salé-Kénitra')),
    ('05', _('Béni Mellal-Khénifra')),
    ('06', _('Casablanca-Settat')),
    ('07', _('Marrakech-Safi')),
    ('08', _('Drâa-Tafilalet')),
    ('09', _('Souss-Massa')),
    ('10', _('Guelmim-Oued Noun')),
    ('11', _('Laâyoune-Sakia El Hamra')),
    ('12', _('Dakhla-Oued Ed Dahab')),
)
