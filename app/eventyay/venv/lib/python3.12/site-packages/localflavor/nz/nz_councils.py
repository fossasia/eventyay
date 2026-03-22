"""
New Zealand (North and South Island) city and district councils.

Source: http://en.wikipedia.org/wiki/Territorial_authorities_of_New_Zealand

District council choices are in format:

    ('Name', _('Name District')),

eg.
    ('Selwyn', _('Selwyn District')),


City council choices are in format:

    ('Name', _('Name')),

eg.
    ('Christchurch', _('Christchurch')),


"""

from django.utils.translation import gettext_lazy as _

#: A list of North Island city and district councils
NORTH_ISLAND_COUNCIL_CHOICES = (
    ('Far North', _('Far North District')),
    ('Whangarei', _('Whangarei District')),
    ('Kaipara', _('Kaipara District')),
    ('Auckland', _('Auckland')),
    ('Thames-Coromandel', _('Thames-Coromandel District')),
    ('Hauraki', _('Hauraki District')),
    ('Waikato', _('Waikato District')),
    ('Matamata-Piako', _('Matamata-Piako District')),
    ('Hamilton', _('Hamilton')),
    ('Waipa', _('Waipa District')),
    ('South Waikato', _('South Waikato District')),
    ('Otorohanga', _('Otorohanga District')),
    ('Waitomo', _('Waitomo District')),
    ('Taupo', _('Taupo District')),
    ('Western Bay of Plenty', _('Western Bay of Plenty District')),
    ('Tauranga', _('Tauranga')),
    ('Opotiki', _('Opotiki District')),
    ('Whakatane', _('Whakatane District')),
    ('Rotorua	', _('Rotorua District')),
    ('Kawerau', _('Kawerau District')),
    ('Gisborne', _('Gisborne District')),
    ('Wairoa', _('Wairoa District')),
    ('Hastings', _('Hastings District')),
    ('Napier', _('Napier')),
    ('Central Hawke\'s Bay', _('Central Hawke\'s Bay District')),
    ('New Plymouth', _('New Plymouth District')),
    ('Stratford', _('Stratford District')),
    ('South Taranaki', _('South Taranaki District')),
    ('Ruapehu', _('Ruapehu District')),
    ('Rangitikei', _('Rangitikei District')),
    ('Wanganui', _('Wanganui District')),
    ('Manawatu', _('Manawatu District')),
    ('Palmerston North', _('Palmerston North')),
    ('Tararua', _('Tararua District')),
    ('Horowhenua', _('Horowhenua District')),
    ('Masterton', _('Masterton District')),
    ('Kapiti Coast', _('Kapiti Coast District')),
    ('Carterton', _('Carterton District')),
    ('South Wairarapa', _('South Wairarapa District')),
    ('Upper Hutt', _('Upper Hutt')),
    ('Porirua', _('Porirua')),
    ('Hutt', _('Hutt')),
    ('Wellington', _('Wellington')),
)


#: A list of South Island city and district councils
SOUTH_ISLAND_COUNCIL_CHOICES = (
    ('Tasman', _('Tasman District')),
    ('Nelson', _('Nelson')),
    ('Marlborough', _('Marlborough District')),
    ('Buller', _('Buller District')),
    ('Grey', _('Grey District')),
    ('Westland', _('Westland District')),
    ('Kaikoura', _('Kaikoura District')),
    ('Hurunui', _('Hurunui District')),
    ('Selwyn', _('Selwyn District')),
    ('Waimakariri', _('Waimakariri District')),
    ('Christchurch', _('Christchurch')),
    ('Ashburton', _('Ashburton District')),
    ('Mackenzie', _('Mackenzie District')),
    ('Timaru', _('Timaru District')),
    ('Waimate', _('Waimate District')),
    ('Waitaki', _('Waitaki District')),
    ('Queenstown-Lakes', _('Queenstown-Lakes District')),
    ('Central Otago', _('Central Otago District')),
    ('Dunedin', _('Dunedin')),
    ('Clutha', _('Clutha District')),
    ('Southland', _('Southland District')),
    ('Gore', _('Gore District')),
    ('Invercargill', _('Invercargill')),
)
