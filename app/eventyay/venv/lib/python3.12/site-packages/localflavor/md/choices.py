from django.utils.translation import gettext_lazy as _

COMPANY_TYPES_CHOICES = (
    ('II', _('Întreprindere Individuală')),
    ('SA', _('Societate pe acţiuni')),
    ('SNC', _('Societate în nume colectiv')),
    ('SC', _('Societatea în comandită')),
    ('CP', _('Cooperativa de producţie')),
    ('CI', _('Cooperativa de întreprinzători')),
    ('SRL', _('Societate cu răspundere limitată')),
    ('GT', _('Gospodăria ţărănească')),
)

LICENSE_PLATE_DIPLOMATIC = (
    ('CD', _('Diplomatic Corps')),
    ('TS', _('Service Staff')),
    ('TC', _('Consular Staff')),
    ('CA', _('Administrative body')),
)

LICENSE_PLATE_POLICE = (
    ('MAI', _('Ministry of Internal Affairs')),
    ('MIC', _('Carabinieri Subdivision')),
    ('FA', _('Military Forces')),
    ('DG', _('Border Control')),
)

LICENSE_PLATE_GOVERNMENT_TYPE = (
    ('P', _('Parliament')),
    ('G', _('Government')),
    ('A', _('Chancellery')),
)

REGION_CHOICES_2002_2015 = (
    ('AN', _('Anenii Noi')),
    ('BE', _('Tighina')),
    ('BL', _('Bălți')),
    ('BR', _('Briceni')),
    ('BS', _('Basarabeasca')),
    ('C', _('Chișinău')),
    ('CC', _('Camenca')),
    ('CG', _('Ceadîr-Lunga')),
    ('CH', _('Cahul')),
    ('CL', _('Călărași')),
    ('CM', _('Cimișlia')),
    ('CN', _('Căinari')),
    ('CO', _('Comrat')),
    ('CR', _('Criuleni')),
    ('CS', _('Căușeni')),
    ('CT', _('Cantemir')),
    ('DB', _('Dubăsari')),
    ('DN', _('Dondușeni')),
    ('DR', _('Drochia')),
    ('ED', _('Edineț')),
    ('FL', _('Fălești')),
    ('FR', _('Florești')),
    ('GE', _('Gagauzia')),
    ('GL', _('Glodeni')),
    ('GR', _('Grigoriopol')),
    ('HN', _('Hîncești')),
    ('IL', _('Ialoveni')),
    ('K', _('Chișinău')),  # duplicate key for Chișinău (a.k.a. 'Kishinev')
    ('LV', _('Leova')),
    ('NS', _('Nisporeni')),
    ('OC', _('Ocnița')),
    ('OR', _('Orhei')),
    ('RB', _('Rîbnița')),
    ('RS', _('Rîșcani')),
    ('RZ', _('Rezina')),
    ('SD', _('Șoldănești')),
    ('SG', _('Sîngerei')),
    ('SL', _('Slobozia')),
    ('SR', _('Soroca')),
    ('ST', _('Strășeni')),
    ('SV', _('Ștefan Vodă')),
    ('TG', _('Tighina')),
    ('TR', _('Taraclia')),
    ('TL', _('Telenești')),
    ('UN', _('Ungheni')),
    ('VL', _('Vulcănești')),
)
