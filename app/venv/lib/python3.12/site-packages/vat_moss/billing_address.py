# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
from decimal import Decimal

try:
    # Python 2
    str_cls = unicode
except (NameError):
    # Python 3
    str_cls = str

from . import rates


def calculate_rate(country_code, postal_code, city):
    """
    Calculates the VAT rate that should be collected based on address
    information provided

    :param country_code:
        The two-character country code

    :param postal_code:
        The postal code for the user

    :param city:
        The city name for the user

    :raises:
        ValueError - If country code is not two characers, or postal_code or city are not strings. postal_code may be None or blank string for countries without postal codes.

    :return:
        A tuple of (Decimal percentage rate, country code, exception name [or None])
    """

    if not country_code or not isinstance(country_code, str_cls):
        raise ValueError('Invalidly formatted country code')

    country_code = country_code.strip()
    if len(country_code) != 2:
        raise ValueError('Invalidly formatted country code')

    country_code = country_code.upper()

    if country_code not in COUNTRIES_WITHOUT_POSTAL_CODES:
        if not postal_code or not isinstance(postal_code, str_cls):
            raise ValueError('Postal code is not a string')

    if not city or not isinstance(city, str_cls):
        raise ValueError('City is not a string')

    if isinstance(postal_code, str_cls):
        postal_code = re.sub('\\s+', '', postal_code)
        postal_code = postal_code.upper()

        # Remove the common european practice of adding the country code
        # to the beginning of a postal code, followed by a dash
        if len(postal_code) > 3 and postal_code[0:3] == country_code + '-':
            postal_code = postal_code[3:]

        postal_code = postal_code.replace('-', '')

    city = city.lower().strip()

    if country_code not in rates.BY_COUNTRY and country_code not in POSTAL_CODE_EXCEPTIONS:
        return (Decimal('0.0'), country_code, None)

    country_default = rates.BY_COUNTRY.get(country_code, {'rate': Decimal('0.0')})['rate']

    if country_code not in POSTAL_CODE_EXCEPTIONS:
        return (country_default, country_code, None)

    exceptions = POSTAL_CODE_EXCEPTIONS[country_code]
    for matcher in exceptions:
        # Postal code-only match
        if isinstance(matcher, str_cls):
            postal_regex = matcher
            city_regex = None
        else:
            postal_regex, city_regex = matcher

        if not re.match(postal_regex, postal_code):
            continue

        if city_regex and not re.search(city_regex, city):
            continue

        mapped_country = exceptions[matcher]['country_code']

        # There is at least one entry where we map to a different country,
        # but are not mapping to an exception
        if 'name' not in exceptions[matcher]:
            country_code = mapped_country
            country_default = rates.BY_COUNTRY[country_code]['rate']
            break

        mapped_name = exceptions[matcher]['name']

        rate = rates.BY_COUNTRY[mapped_country]['exceptions'][mapped_name]
        return (rate, mapped_country, mapped_name)

    return (country_default, country_code, None)


# A dictionary of countries, each being dictionary with keys that are either
# a string postal code regex, or a tuple of postal code regex and city name
# regex.
#
# There is a country_code value because some jurisdictions have post offices
# through multiple countries.
#
# These should only be used with billing addresses.
POSTAL_CODE_EXCEPTIONS = {
    'AT': {
        '^6691$': {
            'country_code': 'AT',
            'name': 'Jungholz'
        },
        ('^699[123]$', '\\bmittelberg\\b'): {
            'country_code': 'AT',
            'name': 'Mittelberg'
        }
    },
    'CH': {
        '^8238$': {
            'country_code': 'DE',
            'name': 'Büsingen am Hochrhein'
        },
        '^6911$': {
            'country_code': 'IT',
            'name': "Campione d'Italia"
        },
        # The Italian city of Domodossola has a Swiss post office also
        '^3907$': {
            'country_code': 'IT'
        }
    },
    'DE': {
        '^87491$': {
            'country_code': 'AT',
            'name': 'Jungholz'
        },
        ('^8756[789]$', '\\bmittelberg\\b'): {
            'country_code': 'AT',
            'name': 'Mittelberg'
        },
        '^78266$': {
            'country_code': 'DE',
            'name': 'Büsingen am Hochrhein'
        },
        '^27498$': {
            'country_code': 'DE',
            'name': 'Heligoland'
        }
    },
    'ES': {
        '^(5100[1-5]|5107[0-1]|51081)$': {
            'country_code': 'ES',
            'name': 'Ceuta'
        },
        '^(5200[0-6]|5207[0-1]|52081)$': {
            'country_code': 'ES',
            'name': 'Melilla'
        },
        '^(35\\d{3}|38\\d{3})$': {
            'country_code': 'ES',
            'name': 'Canary Islands'
        }
    },
    # The UK RAF bases in Cyprus are taxed at the Cyprus rate
    'GB': {
        # Akrotiri
        '^BFPO57|BF12AT$': {
            'country_code': 'CY'
        },
        # Dhekelia
        '^BFPO58|BF12AU$': {
            'country_code': 'CY'
        }
    },
    'GR': {
        '^63086$': {
            'country_code': 'GR',
            'name': 'Mount Athos'
        }
    },
    'IT': {
        ('^22060$', '\\bcampione\\b'): {
            'country_code': 'IT',
            'name': "Campione d'Italia"
        },
        ('^23030$', '\\blivigno\\b'): {
            'country_code': 'IT',
            'name': 'Livigno'
        }
    },
    'PT': {
        '^9[0-4]\\d{2,}$': {
            'country_code': 'PT',
            'name': 'Madeira'
        },
        '^9[5-9]\\d{2,}$': {
            'country_code': 'PT',
            'name': 'Azores'
        }
    }
}


COUNTRIES_WITHOUT_POSTAL_CODES = {
    'AE': True,
    'AG': True,
    'AN': True,
    'AO': True,
    'AW': True,
    'BF': True,
    'BI': True,
    'BJ': True,
    'BS': True,
    'BW': True,
    'BZ': True,
    'CD': True,
    'CF': True,
    'CG': True,
    'CI': True,
    'CK': True,
    'CM': True,
    'DJ': True,
    'DM': True,
    'ER': True,
    'FJ': True,
    'GD': True,
    'GH': True,
    'GM': True,
    'GN': True,
    'GQ': True,
    'GY': True,
    'HK': True,
    'IE': True,
    'JM': True,
    'KE': True,
    'KI': True,
    'KM': True,
    'KN': True,
    'KP': True,
    'LC': True,
    'ML': True,
    'MO': True,
    'MR': True,
    'MS': True,
    'MU': True,
    'MW': True,
    'NR': True,
    'NU': True,
    'PA': True,
    'QA': True,
    'RW': True,
    'SA': True,
    'SB': True,
    'SC': True,
    'SL': True,
    'SO': True,
    'SR': True,
    'ST': True,
    'SY': True,
    'TF': True,
    'TK': True,
    'TL': True,
    'TO': True,
    'TT': True,
    'TV': True,
    'TZ': True,
    'UG': True,
    'VU': True,
    'YE': True,
    'ZA': True,
    'ZW': True
}
