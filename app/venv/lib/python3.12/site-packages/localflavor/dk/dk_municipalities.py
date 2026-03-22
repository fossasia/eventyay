from django.utils.translation import gettext_lazy as _

#: A list of municipalities in the Danish region Hovedstaden
#: as `choices` in a formfield.
REGION_HOVEDSTADEN = [
    ('albertslund', _('Albertslund')),
    ('alleroed', _('Allerød')),
    ('ballerup', _('Ballerup')),
    ('bornholm', _('Bornholm')),
    ('broendby', _('Brøndby')),
    ('dragoer', _('Dragør')),
    ('egedal', _('Egedal')),
    ('fredensborg', _('Fredensborg')),
    ('frederiksberg', _('Frederiksberg')),
    ('frederikssund', _('Frederikssund')),
    ('furesoe', _('Furesø')),
    ('gentofte', _('Gentofte')),
    ('gladsaxe', _('Gladsaxe')),
    ('glostrup', _('Glostrup')),
    ('gribskov', _('Gribskov')),
    ('halsnaes', _('Halsnæs')),
    ('helsingoer', _('Helsingør')),
    ('herlev', _('Herlev')),
    ('hilleroed', _('Hillerød')),
    ('hvidovre', _('Hvidovre')),
    ('hoeje-taastrup', _('Høje-Taastrup')),
    ('hoersholm', _('Hørsholm')),
    ('ishoej', _('Ishøj')),
    ('koebenhavn', _('København')),
    ('lyngby-taarbaek', _('Lyngby-Taarbæk')),
    ('rudersdal', _('Rudersdal')),
    ('roedovre', _('Rødovre')),
    ('taarnby', _('Tårnby')),
    ('vallensbaek', _('Vallensbæk')),
]

#: A list of municipalities in the Danish region Midtjylland
#: as `choices` in a formfield.
REGION_MIDTJYLLAND = [
    ('favrskov', _('Favrskov')),
    ('hedensted', _('Hedensted')),
    ('herning', _('Herning')),
    ('holstebro', _('Holstebro')),
    ('horsens', _('Horsens')),
    ('ikast-Brande', _('Ikast-Brande')),
    ('lemvig', _('Lemvig')),
    ('norddjurs', _('Norddjurs')),
    ('odder', _('Odder')),
    ('randers', _('Randers')),
    ('ringkoebing-skjern', _('Ringkøbing-Skjern')),
    ('samsoe', _('Samsø')),
    ('silkeborg', _('Silkeborg')),
    ('skanderborg', _('Skanderborg')),
    ('skive', _('Skive')),
    ('struer', _('Struer')),
    ('syddjurs', _('Syddjurs')),
    ('viborg', _('Viborg')),
    ('aarhus', _('Aarhus')),
]

#: A list of municipalities in the Danish region Nordjylland
#: as `choices` in a formfield.
REGION_NORDJYLLAND = [
    ('broenderslev', _('Brønderslev')),
    ('frederikshavn', _('Frederikshavn')),
    ('hjoerring', _('Hjørring')),
    ('jammerbugt', _('Jammerbugt')),
    ('laesoe', _('Læsø')),
    ('mariagerfjord', _('Mariagerfjord')),
    ('morsoe', _('Morsø')),
    ('rebild', _('Rebild')),
    ('thisted', _('Thisted')),
    ('vesthimmerland', _('Vesthimmerland')),
    ('aalborg', _('Aalborg')),
]

#: A list of municipalities in the Danish region Sjælland
#: as `choices` in a formfield.
REGION_SJAELLAND = [
    ('faxe', _('Faxe')),
    ('greve', _('Greve')),
    ('guldborgsund', _('Guldborgsund')),
    ('holbaek', _('Holbæk')),
    ('kalundborg', _('Kalundborg')),
    ('koege', _('Køge')),
    ('lejre', _('Lejre')),
    ('lolland', _('Lolland')),
    ('naestved', _('Næstved')),
    ('odsherred', _('Odsherred')),
    ('ringsted', _('Ringsted')),
    ('roskilde', _('Roskilde')),
    ('slagelse', _('Slagelse')),
    ('solroed', _('Solrød')),
    ('soroe', _('Sorø')),
    ('stevns', _('Stevns')),
    ('vordingborg', _('Vordingborg')),
]

#: A list of municipalities in the Danish region Syddanmark
#: as `choices` in a formfield.
REGION_SYDDANMARK = [
    ('assens', _('Assens')),
    ('billund', _('Billund')),
    ('esbjerg', _('Esbjerg')),
    ('fanoe', _('Fanø')),
    ('fredericia', _('Fredericia')),
    ('faaborg-Midtfyn', _('Faaborg-Midtfyn')),
    ('haderslev', _('Haderslev')),
    ('kerteminde', _('Kerteminde')),
    ('kolding', _('Kolding')),
    ('langeland', _('Langeland')),
    ('middelfart', _('Middelfart')),
    ('nordfyn', _('Nordfyn')),
    ('nyborg', _('Nyborg')),
    ('odense', _('Odense')),
    ('svendborg', _('Svendborg')),
    ('soenderborg', _('Sønderborg')),
    ('toender', _('Tønder')),
    ('varde', _('Varde')),
    ('vejen', _('Vejen')),
    ('vejle', _('Vejle')),
    ('aeroe', _('Ærø')),
    ('aabenraa', _('Aabenraa')),
]

#: A list of Danish municipalities grouped by region.
DK_MUNICIPALITIES = [
    (_('Region Hovedstaden'), REGION_HOVEDSTADEN),
    (_('Region Midtjylland'), REGION_MIDTJYLLAND),
    (_('Region Nordjylland'), REGION_NORDJYLLAND),
    (_('Region Sjælland'), REGION_SJAELLAND),
    (_('Region Syddanmark'), REGION_SYDDANMARK),
]
