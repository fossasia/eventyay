"""
This module contains various lists of regions and subdivisions in Great Britain.

Since subdivisions aren't clear this is supposed to be
the most pragmatic collection of lists as possible. Your mileage may vary.

See https://github.com/django/django-localflavor/pull/43 for a long discussion
about it.

.. versionchanged:: 1.1

"""

from django.utils.translation import gettext_lazy as _

#: Metropolitan and non-metropolitan counties of England
#: (not the ceremonial counties)
#: Retrieved 10th Nov 2014 from http://en.wikipedia.org/wiki/Metropolitan_and_non-metropolitan_counties_of_England
ENGLAND_REGION_CHOICES = (
    ("Bath and North East Somerset", _("Bath and North East Somerset")),
    ("Bedford", _("Bedford")),
    ("Berkshire", _("Berkshire")),
    ("Blackburn with Darwen", _("Blackburn with Darwen")),
    ("Blackpool", _("Blackpool")),
    ("Bournemouth", _("Bournemouth")),
    ("Brighton & Hove", _("Brighton & Hove")),
    ("Bristol", _("Bristol")),
    ("Buckinghamshire", _("Buckinghamshire")),
    ("Cambridgeshire", _("Cambridgeshire")),
    ("Central Bedfordshire", _("Central Bedfordshire")),
    ("Cheshire East", _("Cheshire East")),
    ("Cheshire West and Chester", _("Cheshire West and Chester")),
    ("Cornwall", _("Cornwall")),
    ("Cumbria", _("Cumbria")),
    ("Darlington", _("Darlington")),
    ("Derby", _("Derby")),
    ("Derbyshire", _("Derbyshire")),
    ("Devon", _("Devon")),
    ("Dorset", _("Dorset")),
    ("Durham", _("Durham")),
    ("East Riding of Yorkshire", _("East Riding of Yorkshire")),
    ("East Sussex", _("East Sussex")),
    ("Essex", _("Essex")),
    ("Gloucestershire", _("Gloucestershire")),
    ("Greater Manchester", _("Greater Manchester")),
    ("Halton", _("Halton")),
    ("Hampshire", _("Hampshire")),
    ("Hartlepool", _("Hartlepool")),
    ("Herefordshire", _("Herefordshire")),
    ("Hertfordshire", _("Hertfordshire")),
    ("Isle of Wight", _("Isle of Wight")),
    ("Kent", _("Kent")),
    ("Kingston upon Hull", _("Kingston upon Hull")),
    ("Lancashire", _("Lancashire")),
    ("Leicester", _("Leicester")),
    ("Leicestershire", _("Leicestershire")),
    ("Lincolnshire", _("Lincolnshire")),
    ("London", _("London")),
    ("Luton", _("Luton")),
    ("Medway", _("Medway")),
    ("Merseyside", _("Merseyside")),
    ("Middlesbrough", _("Middlesbrough")),
    ("Milton Keynes", _("Milton Keynes")),
    ("Norfolk", _("Norfolk")),
    ("North East Lincolnshire", _("North East Lincolnshire")),
    ("North Lincolnshire", _("North Lincolnshire")),
    ("North Somerset", _("North Somerset")),
    ("North Yorkshire", _("North Yorkshire")),
    ("Northamptonshire", _("Northamptonshire")),
    ("Northumberland", _("Northumberland")),
    ("Nottingham", _("Nottingham")),
    ("Nottinghamshire", _("Nottinghamshire")),
    ("Oxfordshire", _("Oxfordshire")),
    ("Peterborough", _("Peterborough")),
    ("Plymouth", _("Plymouth")),
    ("Poole", _("Poole")),
    ("Portsmouth", _("Portsmouth")),
    ("Redcar and Cleveland", _("Redcar and Cleveland")),
    ("Rutland", _("Rutland")),
    ("Shropshire", _("Shropshire")),
    ("Somerset", _("Somerset")),
    ("South Gloucestershire", _("South Gloucestershire")),
    ("South Yorkshire", _("South Yorkshire")),
    ("Southampton", _("Southampton")),
    ("Southend-on-Sea", _("Southend-on-Sea")),
    ("Staffordshire", _("Staffordshire")),
    ("Stockton-on-Tees", _("Stockton-on-Tees")),
    ("Stoke-on-Trent", _("Stoke-on-Trent")),
    ("Suffolk", _("Suffolk")),
    ("Surrey", _("Surrey")),
    ("Swindon", _("Swindon")),
    ("Telford and Wrekin", _("Telford and Wrekin")),
    ("Thurrock", _("Thurrock")),
    ("Torbay", _("Torbay")),
    ("Tyne and Wear", _("Tyne and Wear")),
    ("Warrington", _("Warrington")),
    ("Warwickshire", _("Warwickshire")),
    ("West Midlands", _("West Midlands")),
    ("West Sussex", _("West Sussex")),
    ("West Yorkshire", _("West Yorkshire")),
    ("Wiltshire", _("Wiltshire")),
    ("Worcestershire", _("Worcestershire")),
    ("York", _("York"))
)


#: Counties of Northern Ireland
#: (not the more recent, but less well-known, districts of Northern Ireland)
#: Retrieved 10th Nov 2014 from http://en.wikipedia.org/wiki/Counties_of_Northern_Ireland
NORTHERN_IRELAND_REGION_CHOICES = (
    ("Antrim", _("Antrim")),
    ("Armagh", _("Armagh")),
    ("Down", _("Down")),
    ("Fermanagh", _("Fermanagh")),
    ("Londonderry", _("Londonderry")),
    ("Tyrone", _("Tyrone"))
)


#: Principal areas of Wales
#: (not the preserved or historic counties)
#: Retrieved 10th Nov 2014 from http://en.wikipedia.org/wiki/Local_government_in_Wales
WALES_REGION_CHOICES = (
    ("Blaenau Gwent", _("Blaenau Gwent")),
    ("Bridgend", _("Bridgend")),
    ("Caerphilly", _("Caerphilly")),
    ("Cardiff", _("Cardiff")),
    ("Carmarthenshire", _("Carmarthenshire")),
    ("Ceredigion", _("Ceredigion")),
    ("Conwy", _("Conwy")),
    ("Denbighshire", _("Denbighshire")),
    ("Flintshire", _("Flintshire")),
    ("Gwynedd", _("Gwynedd")),
    ("Isle of Anglesey", _("Isle of Anglesey")),
    ("Merthyr Tydfil", _("Merthyr Tydfil")),
    ("Monmouthshire", _("Monmouthshire")),
    ("Neath Port Talbot", _("Neath Port Talbot")),
    ("Newport", _("Newport")),
    ("Pembrokeshire", _("Pembrokeshire")),
    ("Powys", _("Powys")),
    ("Rhondda Cynon Taf", _("Rhondda Cynon Taf")),
    ("Swansea", _("Swansea")),
    ("Torfaen", _("Torfaen")),
    ("Vale of Glamorgan", _("Vale of Glamorgan")),
    ("Wrexham", _("Wrexham"))
)


#: Council areas of Scotland
#: Retrieved 10th Nov 2014 from http://en.wikipedia.org/wiki/Subdivisions_of_Scotland#Council_areas
SCOTTISH_REGION_CHOICES = (
    ("Aberdeen City", _("Aberdeen City")),
    ("Aberdeenshire", _("Aberdeenshire")),
    ("Angus", _("Angus")),
    ("Argyll and Bute", _("Argyll and Bute")),
    ("Clackmannanshire", _("Clackmannanshire")),
    ("Dumfries and Galloway", _("Dumfries and Galloway")),
    ("Dundee City", _("Dundee City")),
    ("East Ayrshire", _("East Ayrshire")),
    ("East Dunbartonshire", _("East Dunbartonshire")),
    ("East Lothian", _("East Lothian")),
    ("East Renfrewshire", _("East Renfrewshire")),
    ("Edinburgh, City of ", _("Edinburgh, City of")),
    ("Falkirk", _("Falkirk")),
    ("Fife", _("Fife")),
    ("Glasgow City", _("Glasgow City")),
    ("Highland", _("Highland")),
    ("Inverclyde", _("Inverclyde")),
    ("Midlothian", _("Midlothian")),
    ("Moray", _("Moray")),
    ("North Ayrshire", _("North Ayrshire")),
    ("North Lanarkshire", _("North Lanarkshire")),
    ("Perth and Kinross", _("Perth and Kinross")),
    ("Renfrewshire", _("Renfrewshire")),
    ("Scottish Borders", _("Scottish Borders")),
    ("South Ayrshire", _("South Ayrshire")),
    ("South Lanarkshire", _("South Lanarkshire")),
    ("Stirling", _("Stirling")),
    ("West Dunbartonshire", _("West Dunbartonshire")),
    ("West Lothian", _("West Lothian")),
    ("Na h-Eileanan Siar", _("Na h-Eileanan Siar")),
    ("Orkney Islands", _("Orkney Islands")),
    ("Shetland Islands", _("Shetland Islands"))
)


#: Nations of the United Kingdom
GB_NATIONS_CHOICES = (
    ("England", _("England")),
    ("Northern Ireland", _("Northern Ireland")),
    ("Wales", _("Wales")),
    ("Scotland", _("Scotland"))
)


#: All regions of United Kingdom
GB_REGION_CHOICES = (ENGLAND_REGION_CHOICES +
                     NORTHERN_IRELAND_REGION_CHOICES +
                     WALES_REGION_CHOICES +
                     SCOTTISH_REGION_CHOICES)
