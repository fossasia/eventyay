"""
Zone wise list of districts of Nepal.

Source: https://en.wikipedia.org/wiki/List_of_zones_of_Nepal

Choices for districts are in this format:

    ('name_of_district', _('Name of district')),
"""

from django.utils.translation import gettext_lazy as _

# list of districts in Bagmati Zone
BAGMATI_DISTRICTS = [ 
    ('bhaktapur', _('Bhaktapur')),
    ('dhading', _('Dhading')),
    ('kathmandu', _('Kathmandu')),
    ('kavrepalanchok', _('Kavrepalanchok')),
    ('lalitpur', _('Lalitpur')),
    ('nuwakot', _('Nuwakot')),
    ('rasuwa', _('Rasuwa')),
    ('sindhupalchok', _('Sindhupalchok')),
]

# list of districts in Bheri Zone
BHERI_DISTRICTS = [
    ('banke', _('Banke')),
    ('bardiya', _('Bardiya')),
    ('dailekh', _('Dailekh')),
    ('jajarkot', _('Jajarkot')),
    ('surkhet', _('Surkhet')),
]

# list of districts in Dhawalagiri Zone
DHAWALAGIRI_DISTRICTS = [
    ('baglung', _('Baglung')),
    ('mustang', _('Mustang')),
    ('myagdi', _('Myagdi')),
    ('parbat', _('Parbat')),
]

# list of districts in Gandaki Zone
GANDAKI_DISTRICTS = [
    ('gorkha', _('Gorkha')),
    ('kaski', _('Kaski')),
    ('lamjung', _('Lamjung')),
    ('manang', _('Manang')),
    ('syangja', _('Syangja')),
    ('tanahu', _('Tanahu')),
]

# list of districts in Janakpur Zone
JANAKPUR_DISTRICTS = [
    ('dhanusa', _('Dhanusa')),
    ('dholkha', _('Dholkha')),
    ('mahottari', _('Mahottari')),
    ('ramechhap', _('Ramechhap')),
    ('sarlahi', _('Sarlahi')),
    ('sindhuli', _('Sindhuli')),
]

# list of districts in Karnali Zone
KARNALI_DISTRICTS = [
    ('dolpa', _('Dolpa')),
    ('humla', _('Humla')),
    ('jumla', _('Jumla')),
    ('kalikot', _('Kalikot')),
    ('mugu', _('Mugu')),
]

# list of districts in Koshi Zone
KOSHI_DISTRICTS = [
    ('bhojpur', _('Bhojpur')),
    ('dhankuta', _('Dhankuta')),
    ('morang', _('Morang')),
    ('sankhuwasabha', _('Sankhuwasabha')),
    ('sunsari', _('Sunsari')),
    ('terhathum', _('Terhathum')),
]

# list of districts in Lumbini Zone
LUMBINI_DISTRICTS = [
    ('arghakhanchi', _('Arghakhanchi')),
    ('gulmi', _('Gulmi')),
    ('kapilvastu', _('Kapilvastu')),
    ('nawalparasi', _('Nawalparasi')),
    ('palpa', _('Palpa')),
    ('rupandehi', _('Rupandehi')),
]

# list of districts in Mahakali Zone
MAHAKALI_DISTRICTS = [ 
    ('baitadi', _('Baitadi')),
    ('dadeldhura', _('Dadeldhura')),
    ('darchula', _('Darchula')),
    ('kanchanpur', _('Kanchanpur')),
]

# list of districts in Mechi Zone
MECHI_DISTRICTS = [
    ('ilam', _('Ilam')),
    ('jhapa', _('Jhapa')),
    ('panchthar', _('Panchthar')),
    ('taplejung', _('Taplejung')),
]

# list of districts in Narayani Zone
NARAYANI_DISTRICTS = [
    ('bara', _('Bara')),
    ('chitwan', _('Chitwan')),
    ('makwanpur', _('Makwanpur')),
    ('parsa', _('Parsa')),
    ('rautahat', _('Rautahat')),
]

# list of districts in Rapti Zone
RAPTI_DISTRICTS = [
    ('dang_deukhuri', _('Dang Deukhuri')),
    ('pyuthan', _('Pyuthan')),
    ('rolpa', _('Rolpa')),
    ('rukum', _('Rukum')),
    ('salyan', _('Salyan')),
]

# list of districts in Sagarmatha Zone
SAGARMATHA_DISTRICTS = [
    ('khotang', _('Khotang')),
    ('okhaldhunga', _('Okhaldhunga')),
    ('saptari', _('Saptari')),
    ('siraha', _('Siraha')),
    ('solukhumbu', _('Solukhumbu')),
    ('udayapur', _('Udayapur')),
]

# list of districts in Seti Zone
SETI_DISTRICTS = [
    ('achham', _('Achham')),
    ('bajhang', _('Bajhang')),
    ('bajura', _('Bajura')),
    ('doti', _('Doti')),
    ('kailali', _('Kailali')),
]

# list of all districts of Nepal.
DISTRICTS = BAGMATI_DISTRICTS + BHERI_DISTRICTS + DHAWALAGIRI_DISTRICTS + GANDAKI_DISTRICTS +JANAKPUR_DISTRICTS + KARNALI_DISTRICTS + KOSHI_DISTRICTS \
    + LUMBINI_DISTRICTS + MAHAKALI_DISTRICTS  + MECHI_DISTRICTS + NARAYANI_DISTRICTS  + RAPTI_DISTRICTS + SAGARMATHA_DISTRICTS + SETI_DISTRICTS

# alphabetically sorting list of all districts
DISTRICTS.sort(key= lambda district: district[0])
