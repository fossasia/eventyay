from .it_province import PROVINCES

#: An alphabetical list of regions
REGION_CHOICES = (
    ('ABR', 'Abruzzo'),
    ('BAS', 'Basilicata'),
    ('CAL', 'Calabria'),
    ('CAM', 'Campania'),
    ('EMR', 'Emilia-Romagna'),
    ('FVG', 'Friuli-Venezia Giulia'),
    ('LAZ', 'Lazio'),
    ('LIG', 'Liguria'),
    ('LOM', 'Lombardia'),
    ('MAR', 'Marche'),
    ('MOL', 'Molise'),
    ('PMN', 'Piemonte'),
    ('PUG', 'Puglia'),
    ('SAR', 'Sardegna'),
    ('SIC', 'Sicilia'),
    ('TOS', 'Toscana'),
    ('TAA', 'Trentino-Alto Adige'),
    ('UMB', 'Umbria'),
    ('VAO', 'Valle d’Aosta'),
    ('VEN', 'Veneto'),
)

#: A dictionary of regions mapped to provinces
REGION_PROVINCES = {}
for region, _ in REGION_CHOICES:
    REGION_PROVINCES[region] = sorted([p[0] for p in PROVINCES if p[2] == region])

#: A alphabetical list of provinces mapped to regions
REGION_PROVINCE_CHOICES = []
for region, region_name in REGION_CHOICES:
    REGION_PROVINCE_CHOICES.append((region_name, () + tuple((p[0], p[1]) for p in PROVINCES if p[2] == region)))
