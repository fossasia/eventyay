# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal


# The rates used here are pull from the following sources December 17, 2014:
#
# http://ec.europa.eu/taxation_customs/resources/documents/taxation/vat/how_vat_works/rates/vat_rates_en.pdf
# http://www.skatteetaten.no/en/Bedrift-og-organisasjon/Merverdiavgift/Guide-to-Value-Added-Tax-in-Norway/?chapter=3732#kapitteltekst
# http://en.wikipedia.org/wiki/Special_member_state_territories_and_the_European_Union
#
# The following is an extrapolation of special EU VAT rates and exemptions
# listed in the above PDF.
#
#   VAT Does Not Apply
#
#     Countries
#
#       FO - Faroe Islands - Denmark
#       GL - Greenland - Denmark
#       AX - Åland Islands - Finland
#       GF - French Guiana - France
#
#     Cities or regions
#
#       Canary Islands - Spain
#       Melilla - Spain
#       Ceuta - Spain
#       Büsingen am Hochrhein - Germany
#       Heligoland - Germany
#       Mount Athos - Greece
#       Campione d'Italia - Italy
#       Livigno - Italy
#
#     French overseas departments - these have a VAT similar to EU, but they are
#     not actually part of the EU VAT system, so you do not have to collect VAT
#     for e-services. The local VAT is 8.5%.
#     http://ec.europa.eu/taxation_customs/taxation/other_taxes/dock_dues/index_en.htm
#
#       GP - Guadeloupe
#       RE - Réunion
#       MQ - Martinique
#
#   Special VAT Rates
#
#     Monaco - France - 20%
#     Isle of Man - United Kingdom - 20%
#     Azores - Portugal - 18%
#     Madeira - Portugal - 22%
#     Akrotiri - Cyprus - 19%
#     Dhekelia - Cyprus - 19%
#     Jungholz - Austria - 19%
#     Mittelberg - Austria - 19%


# There are country entries and exceptions entries for places that are listed
# on the VAT exceptions list. A value of None means no VAT is to be collected.
BY_COUNTRY = {
    'AT': {  # Austria
        'rate': Decimal('0.20'),
        'exceptions': {
            'Jungholz': Decimal('0.19'),
            'Mittelberg': Decimal('0.19')
        }
    },
    'BE': {  # Belgium
        'rate': Decimal('0.21')
    },
    'BG': {  # Bulgaria
        'rate': Decimal('0.20')
    },
    'CY': {  # Cyprus
        'rate': Decimal('0.19')
    },
    'CZ': {  # Czech Republic
        'rate': Decimal('0.21')
    },
    'DE': {  # Germany
        'rate': Decimal('0.19'),
        'exceptions': {
            'Büsingen am Hochrhein': Decimal('0.0'),
            'Heligoland': Decimal('0.0')
        }
    },
    'DK': {  # Denmark
        'rate': Decimal('0.25')
    },
    'EE': {  # Estonia
        'rate': Decimal('0.20')
    },
    'ES': {  # Spain
        'rate': Decimal('0.21'),
        'exceptions': {
            'Canary Islands': Decimal('0.0'),
            'Ceuta': Decimal('0.0'),
            'Melilla': Decimal('0.0')
        }
    },
    'FI': {  # Finland
        'rate': Decimal('0.24')
    },
    'FR': {  # France
        'rate': Decimal('0.20')
    },
    'GB': {  # United Kingdom
        'rate': Decimal('0.20'),
        'exceptions': {
            # UK RAF Bases in Cyprus are taxed at Cyprus rate
            'Akrotiri': (Decimal('0.19'), 'CY', None),
            'Dhekelia': (Decimal('0.19'), 'CY', None)
        }
    },
    'GR': {  # Greece
        'rate': Decimal('0.23'),
        'exceptions': {
            'Mount Athos': Decimal('0.0')
        }
    },
    'HR': {  # Croatia
        'rate': Decimal('0.25')
    },
    'HU': {  # Hungary
        'rate': Decimal('0.27')
    },
    'IE': {  # Ireland
        'rate': Decimal('0.23')
    },
    'IT': {  # Italy
        'rate': Decimal('0.22'),
        'exceptions': {
            "Campione d'Italia": Decimal('0.0'),
            'Livigno': Decimal('0.0')
        }
    },
    'LT': {  # Lithuania
        'rate': Decimal('0.21')
    },
    'LU': {  # Luxembourg
        'rate': Decimal('0.17')
    },
    'LV': {  # Latvia
        'rate': Decimal('0.21')
    },
    'MT': {  # Malta
        'rate': Decimal('0.18')
    },
    'NL': {  # Netherlands
        'rate': Decimal('0.21')
    },
    'PL': {  # Poland
        'rate': Decimal('0.23')
    },
    'PT': {  # Portugal
        'rate': Decimal('0.23'),
        'exceptions': {
            'Azores': Decimal('0.18'),
            'Madeira': Decimal('0.22')
        }
    },
    'RO': {  # Romania
        'rate': Decimal('0.24')
    },
    'SE': {  # Sweden
        'rate': Decimal('0.25')
    },
    'SI': {  # Slovenia
        'rate': Decimal('0.22')
    },
    'SK': {  # Slovakia
        'rate': Decimal('0.20')
    },

    # Countries associated with EU countries that have a special VAT rate
    'MC': {  # Monaco - France
        'rate': Decimal('0.20')
    },
    'IM': {  # Isle of Man - United Kingdom
        'rate': Decimal('0.20')
    },

    # Non-EU with their own VAT collection requirements
    'NO': {  # Norway
        'rate': Decimal('0.25')
    }
}

