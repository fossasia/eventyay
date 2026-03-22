# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal

try:
    # Python 2
    str_cls = unicode
except (NameError):
    # Python 3
    str_cls = str

from . import rates
from .errors import UndefinitiveError


def calculate_rate(country_code, subdivision, city, address_country_code=None, address_exception=None):
    """
    Calculates the VAT rate from the data returned by a GeoLite2 database

    :param country_code:
        Two-character country code

    :param subdivision:
        The first subdivision name

    :param city:
        The city name

    :param address_country_code:
        The user's country_code, as detected from billing_address or
        declared_residence. This prevents an UndefinitiveError from being
        raised.

    :param address_exception:
        The user's exception name, as detected from billing_address or
        declared_residence. This prevents an UndefinitiveError from being
        raised.

    :raises:
        ValueError - if country code is not two characers, or subdivision or city are not strings
        UndefinitiveError - when no address_country_code and address_exception are provided and the geoip2 information is not specific enough

    :return:
        A tuple of (Decimal percentage rate, country code, exception name [or None])
    """

    if not country_code or not isinstance(country_code, str_cls) or len(country_code) != 2:
        raise ValueError('Invalidly formatted country code')

    if not isinstance(subdivision, str_cls):
        raise ValueError('Subdivision is not a string')

    if not isinstance(city, str_cls):
        raise ValueError('City is not a string')

    country_code = country_code.upper()
    subdivision = subdivision.lower()
    city = city.lower()

    if country_code not in rates.BY_COUNTRY:
        return (Decimal('0.0'), country_code, None)

    country_default = rates.BY_COUNTRY[country_code]['rate']

    if country_code not in GEOIP2_EXCEPTIONS:
        return (country_default, country_code, None)

    exceptions = GEOIP2_EXCEPTIONS[country_code]
    for matcher in exceptions:
        # Subdivision-only match
        if isinstance(matcher, str_cls):
            sub_match = matcher
            city_match = None
        else:
            sub_match, city_match = matcher

        if sub_match != subdivision:
            continue

        if city_match and city_match != city:
            continue

        info = exceptions[matcher]
        exception_name = info['name']
        if not info['definitive']:
            if address_country_code is None:
                raise UndefinitiveError('It is not possible to determine the users VAT rates based on the information provided')

            if address_country_code != country_code:
                continue

            if address_exception != exception_name:
                continue

        rate = rates.BY_COUNTRY[country_code]['exceptions'][exception_name]
        return (rate, country_code, exception_name)

    return (country_default, country_code, None)


# A dictionary that maps information from the GeoLite2 databases to VAT
# exceptions. Top level keys are country codes, each pointing to a dictionary
# with keys that are either a tuple of subdivision name and city name, or just
# a string of subdivision name.
#
# There is a key 'definitive' that indicates is the match is sufficiently
# specific to fully map to the exemption. If 'definitive' is False, other
# methods must be used to obtain place of supply proof.
GEOIP2_EXCEPTIONS = {
    'AT': {
        ('tyrol', 'reutte'): {
            'name': 'Jungholz',
            'definitive': False
        },
        ('vorarlberg', 'mittelberg'): {
            'name': 'Mittelberg',
            'definitive': True
        }
    },
    'DE': {
        ('baden-württemberg region', 'konstanz'): {
            'name': 'Büsingen am Hochrhein',
            'definitive': False
        },
        ('schleswig-holstein', 'pinneberg'): {
            'name': 'Heligoland',
            'definitive': False
        }
    },
    'ES': {
        'canary islands': {
            'name': 'Canary Islands',
            'definitive': True
        },
        'ceuta': {
            'name': 'Ceuta',
            'definitive': True
        },
        'melilla': {
            'name': 'Melilla',
            'definitive': True
        }
    },
    'GR': {
        # There is no direct entry for Mount Athos, so we just flag the
        # Central Macedonia region since it is part of that
        'central macedonia': {
            'name': 'Mount Athos',
            'definitive': False
        }
    },
    'IT': {
        ('lombardy', 'livigno'): {
            'name': 'Livigno',
            'definitive': True
        },
        # There are no entries that cover Campione d'Italia, so instead we
        # just flag the whole region of Lombardy as not definitive.
        'lombardy': {
            'name': "Campione d'Italia",
            'definitive': False
        }
    },
    'PT': {
        'azores': {
            'name': 'Azores',
            'definitive': True
        },
        'madeira': {
            'name': 'Madeira',
            'definitive': True
        }
    }
}
