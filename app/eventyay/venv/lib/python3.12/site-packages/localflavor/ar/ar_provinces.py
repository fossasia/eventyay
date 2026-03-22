from django.utils.translation import gettext_lazy as _

#: A list of Argentinean provinces and autonomous cities as `choices` in a
#: formfield. From http://www.argentina.gov.ar/argentina/portal/paginas.dhtml?pagina=425
PROVINCE_CHOICES = (
    ('B', _('Buenos Aires')),
    ('K', _('Catamarca')),
    ('H', _('Chaco')),
    ('U', _('Chubut')),
    ('C', _('Ciudad Autónoma de Buenos Aires')),
    ('X', _('Córdoba')),
    ('W', _('Corrientes')),
    ('E', _('Entre Ríos')),
    ('P', _('Formosa')),
    ('Y', _('Jujuy')),
    ('L', _('La Pampa')),
    ('F', _('La Rioja')),
    ('M', _('Mendoza')),
    ('N', _('Misiones')),
    ('Q', _('Neuquén')),
    ('R', _('Río Negro')),
    ('A', _('Salta')),
    ('J', _('San Juan')),
    ('D', _('San Luis')),
    ('Z', _('Santa Cruz')),
    ('S', _('Santa Fe')),
    ('G', _('Santiago del Estero')),
    ('V', _('Tierra del Fuego, Antártida e Islas del Atlántico Sur')),
    ('T', _('Tucumán')),
)
