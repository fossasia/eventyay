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
from .errors import UndefinitiveError


def calculate_rate(phone_number, address_country_code=None, address_exception=None):
    """
    Calculates the VAT rate based on a telephone number

    :param phone_number:
        The string phone number, in international format with leading +

    :param address_country_code:
        The user's country_code, as detected from billing_address or
        declared_residence. This prevents an UndefinitiveError from being
        raised.

    :param address_exception:
        The user's exception name, as detected from billing_address or
        declared_residence. This prevents an UndefinitiveError from being
        raised.

    :raises:
        ValueError - error with phone number provided
        UndefinitiveError - when no address_country_code and address_exception are provided and the phone number area code matching isn't specific enough

    :return:
        A tuple of (Decimal percentage rate, country code, exception name [or None])
    """

    if not phone_number:
        raise ValueError('No phone number provided')

    if not isinstance(phone_number, str_cls):
        raise ValueError('Phone number is not a string')

    phone_number = phone_number.strip()
    phone_number = re.sub('[^+0-9]', '', phone_number)

    if not phone_number or phone_number[0] != '+':
        raise ValueError('Phone number is not in international format with a leading +')

    phone_number = phone_number[1:]

    if not phone_number:
        raise ValueError('Phone number does not appear to contain any digits')

    country_code = _lookup_country_code(phone_number)
    if not country_code:
        raise ValueError('Phone number does not appear to be a valid international phone number')

    if country_code in CALLING_CODE_EXCEPTIONS:
        for info in CALLING_CODE_EXCEPTIONS[country_code]:
            if not re.match(info['regex'], phone_number):
                continue

            mapped_country = info['country_code']
            mapped_name = info['name']

            if not info['definitive']:
                if address_country_code is None:
                    raise UndefinitiveError('It is not possible to determine the users VAT rates based on the information provided')

                if address_country_code != mapped_country:
                    continue

                if address_exception != info['name']:
                    continue

            rate = rates.BY_COUNTRY[mapped_country]['exceptions'][mapped_name]
            return (rate, mapped_country, mapped_name)

    if country_code not in rates.BY_COUNTRY:
        return (Decimal('0.0'), country_code, None)

    return (rates.BY_COUNTRY[country_code]['rate'], country_code, None)


def _lookup_country_code(phone_number):
    """
    Accepts an international form of a phone number (+ followed by digits),
    and returns a two-character country code.

    :param phone_number:
        The string phone number, in international format with leading +

    :return:
        A two-character string or None if no match
    """

    leading_digit = phone_number[0]

    if leading_digit not in CALLING_CODE_MAPPING:
        return None

    for mapping in CALLING_CODE_MAPPING[leading_digit]:
        if not re.match(mapping['regex'], phone_number):
            continue
        return mapping['country_code']

    return None


# A list of regular expressions to map against an internation phone number that
# has had the leading + stripped off.
#
# The mapping is in the form:
#
# {
#     digit: [
#         {
#             'regex': regex,
#             'country_code': two character country code
#         }
#     ]
# }
#
# The values are a list so that more specific regexes will be matched first.
# This is necessary since sometimes multiple countries use the same
# international calling code prefix.
CALLING_CODE_MAPPING = {
    '1': [
        {
            'regex': '1(204|226|236|249|250|289|306|343|365|387|403|416|418|431|437|438|450|506|514|519|548|579|581|587|600|604|613|622|633|639|644|647|655|672|677|688|705|709|742|778|780|782|807|819|825|867|873|902|905)',
            'country_code': 'CA'
        },
        {
            'regex': '1268',
            'country_code': 'AG'
        },
        {
            'regex': '1264',
            'country_code': 'AI'
        },
        {
            'regex': '1684',
            'country_code': 'AS'
        },
        {
            'regex': '1246',
            'country_code': 'BB'
        },
        {
            'regex': '1441',
            'country_code': 'BM'
        },
        {
            'regex': '1242',
            'country_code': 'BS'
        },
        {
            'regex': '1767',
            'country_code': 'DM'
        },
        {
            'regex': '1(809|829|849)',
            'country_code': 'DO'
        },
        {
            'regex': '1473',
            'country_code': 'GD'
        },
        {
            'regex': '1671',
            'country_code': 'GU'
        },
        {
            'regex': '1876',
            'country_code': 'JM'
        },
        {
            'regex': '1869',
            'country_code': 'KN'
        },
        {
            'regex': '1345',
            'country_code': 'KY'
        },
        {
            'regex': '1758',
            'country_code': 'LC'
        },
        {
            'regex': '1670',
            'country_code': 'MP'
        },
        {
            'regex': '1664',
            'country_code': 'MS'
        },
        {
            'regex': '1(939|787)',
            'country_code': 'PR'
        },
        {
            'regex': '1721',
            'country_code': 'SX'
        },
        {
            'regex': '1649',
            'country_code': 'TC'
        },
        {
            'regex': '1868',
            'country_code': 'TT'
        },
        {
            'regex': '1784',
            'country_code': 'VC'
        },
        {
            'regex': '1284',
            'country_code': 'VG'
        },
        {
            'regex': '1340',
            'country_code': 'VI'
        },
        {
            'regex': '1',
            'country_code': 'US'
        }
    ],
    '2': [
        {
            'regex': '20',
            'country_code': 'EG'
        },
        {
            'regex': '211',
            'country_code': 'SS'
        },
        {
            'regex': '212(5288|5289)',
            'country_code': 'EH'
        },
        {
            'regex': '212',
            'country_code': 'MA'
        },
        {
            'regex': '213',
            'country_code': 'DZ'
        },
        {
            'regex': '216',
            'country_code': 'TN'
        },
        {
            'regex': '218',
            'country_code': 'LY'
        },
        {
            'regex': '220',
            'country_code': 'GM'
        },
        {
            'regex': '221',
            'country_code': 'SN'
        },
        {
            'regex': '222',
            'country_code': 'MR'
        },
        {
            'regex': '223',
            'country_code': 'ML'
        },
        {
            'regex': '224',
            'country_code': 'GN'
        },
        {
            'regex': '225',
            'country_code': 'CI'
        },
        {
            'regex': '226',
            'country_code': 'BF'
        },
        {
            'regex': '227',
            'country_code': 'NE'
        },
        {
            'regex': '228',
            'country_code': 'TG'
        },
        {
            'regex': '229',
            'country_code': 'BJ'
        },
        {
            'regex': '230',
            'country_code': 'MU'
        },
        {
            'regex': '231',
            'country_code': 'LR'
        },
        {
            'regex': '232',
            'country_code': 'SL'
        },
        {
            'regex': '233',
            'country_code': 'GH'
        },
        {
            'regex': '234',
            'country_code': 'NG'
        },
        {
            'regex': '235',
            'country_code': 'TD'
        },
        {
            'regex': '236',
            'country_code': 'CF'
        },
        {
            'regex': '237',
            'country_code': 'CM'
        },
        {
            'regex': '238',
            'country_code': 'CV'
        },
        {
            'regex': '239',
            'country_code': 'ST'
        },
        {
            'regex': '240',
            'country_code': 'GQ'
        },
        {
            'regex': '241',
            'country_code': 'GA'
        },
        {
            'regex': '242',
            'country_code': 'CG'
        },
        {
            'regex': '243',
            'country_code': 'CD'
        },
        {
            'regex': '244',
            'country_code': 'AO'
        },
        {
            'regex': '245',
            'country_code': 'GW'
        },
        {
            'regex': '246',
            'country_code': 'IO'
        },
        {
            'regex': '247',
            'country_code': 'AC'
        },
        {
            'regex': '248',
            'country_code': 'SC'
        },
        {
            'regex': '249',
            'country_code': 'SD'
        },
        {
            'regex': '250',
            'country_code': 'RW'
        },
        {
            'regex': '251',
            'country_code': 'ET'
        },
        {
            'regex': '252',
            'country_code': 'SO'
        },
        {
            'regex': '253',
            'country_code': 'DJ'
        },
        {
            'regex': '254',
            'country_code': 'KE'
        },
        {
            'regex': '255',
            'country_code': 'TZ'
        },
        {
            'regex': '256',
            'country_code': 'UG'
        },
        {
            'regex': '257',
            'country_code': 'BI'
        },
        {
            'regex': '258',
            'country_code': 'MZ'
        },
        {
            'regex': '260',
            'country_code': 'ZM'
        },
        {
            'regex': '261',
            'country_code': 'MG'
        },
        {
            'regex': '262269',
            'country_code': 'YT'
        },
        {
            'regex': '262',
            'country_code': 'RE'
        },
        {
            'regex': '263',
            'country_code': 'ZW'
        },
        {
            'regex': '264',
            'country_code': 'NA'
        },
        {
            'regex': '265',
            'country_code': 'MW'
        },
        {
            'regex': '266',
            'country_code': 'LS'
        },
        {
            'regex': '267',
            'country_code': 'BW'
        },
        {
            'regex': '268',
            'country_code': 'SZ'
        },
        {
            'regex': '269',
            'country_code': 'KM'
        },
        {
            'regex': '27',
            'country_code': 'ZA'
        },
        {
            'regex': '290',
            'country_code': 'SH'
        },
        {
            'regex': '291',
            'country_code': 'ER'
        },
        {
            'regex': '297',
            'country_code': 'AW'
        },
        {
            'regex': '298',
            'country_code': 'FO'
        },
        {
            'regex': '299',
            'country_code': 'GL'
        }
    ],
    '3': [
        {
            'regex': '30',
            'country_code': 'GR'
        },
        {
            'regex': '31',
            'country_code': 'NL'
        },
        {
            'regex': '32',
            'country_code': 'BE'
        },
        {
            'regex': '33',
            'country_code': 'FR'
        },
        {
            'regex': '34',
            'country_code': 'ES'
        },
        {
            'regex': '350',
            'country_code': 'GI'
        },
        {
            'regex': '351',
            'country_code': 'PT'
        },
        {
            'regex': '352',
            'country_code': 'LU'
        },
        {
            'regex': '353',
            'country_code': 'IE'
        },
        {
            'regex': '354',
            'country_code': 'IS'
        },
        {
            'regex': '355',
            'country_code': 'AL'
        },
        {
            'regex': '356',
            'country_code': 'MT'
        },
        {
            'regex': '357',
            'country_code': 'CY'
        },
        {  # Åland Islands (to exclude from FI)
            'regex': '35818',
            'country_code': 'AX'
        },
        {
            'regex': '358',
            'country_code': 'FI'
        },
        {
            'regex': '359',
            'country_code': 'BG'
        },
        {
            'regex': '36',
            'country_code': 'HU'
        },
        {
            'regex': '370',
            'country_code': 'LT'
        },
        {
            'regex': '371',
            'country_code': 'LV'
        },
        {
            'regex': '372',
            'country_code': 'EE'
        },
        {
            'regex': '373',
            'country_code': 'MD'
        },
        {
            'regex': '374',
            'country_code': 'AM'
        },
        {
            'regex': '375',
            'country_code': 'BY'
        },
        {
            'regex': '376',
            'country_code': 'AD'
        },
        {
            'regex': '377(44|45)',
            'country_code': 'XK'
        },
        {
            'regex': '377',
            'country_code': 'MC'
        },
        {
            'regex': '378',
            'country_code': 'SM'
        },
        {
            'regex': '379',
            'country_code': 'VA'
        },
        {
            'regex': '380',
            'country_code': 'UA'
        },
        {
            'regex': '381(28|29|38|39)',
            'country_code': 'XK'
        },
        {
            'regex': '381',
            'country_code': 'RS'
        },
        {
            'regex': '382',
            'country_code': 'ME'
        },
        {
            'regex': '383',
            'country_code': 'XK'
        },
        {
            'regex': '385',
            'country_code': 'HR'
        },
        {
            'regex': '386(43|49)',
            'country_code': 'XK'
        },
        {
            'regex': '386',
            'country_code': 'SI'
        },
        {
            'regex': '387',
            'country_code': 'BA'
        },
        {
            'regex': '389',
            'country_code': 'MK'
        },
        {
            'regex': '3906698',
            'country_code': 'VA'
        },
        {
            'regex': '39',
            'country_code': 'IT'
        }
    ],
    '4': [
        {
            'regex': '40',
            'country_code': 'RO'
        },
        {
            'regex': '41',
            'country_code': 'CH'
        },
        {
            'regex': '420',
            'country_code': 'CZ'
        },
        {
            'regex': '421',
            'country_code': 'SK'
        },
        {
            'regex': '423',
            'country_code': 'LI'
        },
        {
            'regex': '43',
            'country_code': 'AT'
        },
        {  # Guernsey (to exclude from GB)
            'regex': '44(148|7781|7839|7911)',
            'country_code': 'GG'
        },
        {  # Jersey (to exclude from GB)
            'regex': '44(153|7509|7797|7937|7700|7829)',
            'country_code': 'JE'
        },
        {  # Isle of Man
            'regex': '44(162|7624|7524|7924)',
            'country_code': 'IM'
        },
        {
            'regex': '44',
            'country_code': 'GB'
        },
        {
            'regex': '45',
            'country_code': 'DK'
        },
        {
            'regex': '46',
            'country_code': 'SE'
        },
        {
            'regex': '47',
            'country_code': 'NO'
        },
        {
            'regex': '48',
            'country_code': 'PL'
        },
        {
            'regex': '49',
            'country_code': 'DE'
        }
    ],
    '5': [
        {
            'regex': '500',
            'country_code': 'FK'
        },
        {
            'regex': '501',
            'country_code': 'BZ'
        },
        {
            'regex': '502',
            'country_code': 'GT'
        },
        {
            'regex': '503',
            'country_code': 'SV'
        },
        {
            'regex': '504',
            'country_code': 'HN'
        },
        {
            'regex': '505',
            'country_code': 'NI'
        },
        {
            'regex': '506',
            'country_code': 'CR'
        },
        {
            'regex': '507',
            'country_code': 'PA'
        },
        {
            'regex': '508',
            'country_code': 'PM'
        },
        {
            'regex': '509',
            'country_code': 'HT'
        },
        {
            'regex': '51',
            'country_code': 'PE'
        },
        {
            'regex': '52',
            'country_code': 'MX'
        },
        {
            'regex': '53',
            'country_code': 'CU'
        },
        {
            'regex': '54',
            'country_code': 'AR'
        },
        {
            'regex': '55',
            'country_code': 'BR'
        },
        {
            'regex': '56',
            'country_code': 'CL'
        },
        {
            'regex': '57',
            'country_code': 'CO'
        },
        {
            'regex': '58',
            'country_code': 'VE'
        },
        {
            'regex': '590(590(51|52|58|77|87)|690(10|22|27|66|77|87|88))',
            'country_code': 'MF'
        },
        {
            'regex': '590590(27|29)',
            'country_code': 'BL'
        },
        {
            'regex': '590',
            'country_code': 'GP'
        },
        {
            'regex': '591',
            'country_code': 'BO'
        },
        {
            'regex': '592',
            'country_code': 'GY'
        },
        {
            'regex': '593',
            'country_code': 'EC'
        },
        {
            'regex': '594',
            'country_code': 'GF'
        },
        {
            'regex': '595',
            'country_code': 'PY'
        },
        {
            'regex': '596',
            'country_code': 'MQ'
        },
        {
            'regex': '597',
            'country_code': 'SR'
        },
        {
            'regex': '598',
            'country_code': 'UY'
        },
        {
            'regex': '5999',
            'country_code': 'CW'
        },
        {
            'regex': '599',
            'country_code': 'BQ'
        }
    ],
    '6': [
        {
            'regex': '60',
            'country_code': 'MY'
        },
        {
            'regex': '6189164',
            'country_code': 'CX'
        },
        {
            'regex': '6189162',
            'country_code': 'CC'
        },
        {
            'regex': '61',
            'country_code': 'AU'
        },
        {
            'regex': '62',
            'country_code': 'ID'
        },
        {
            'regex': '63',
            'country_code': 'PH'
        },
        {
            'regex': '64',
            'country_code': 'NZ'
        },
        {
            'regex': '65',
            'country_code': 'SG'
        },
        {
            'regex': '66',
            'country_code': 'TH'
        },
        {
            'regex': '670',
            'country_code': 'TL'
        },
        {
            'regex': '6723',
            'country_code': 'NF'
        },
        {
            'regex': '6721',
            'country_code': 'AQ'
        },
        {
            'regex': '673',
            'country_code': 'BN'
        },
        {
            'regex': '674',
            'country_code': 'NR'
        },
        {
            'regex': '675',
            'country_code': 'PG'
        },
        {
            'regex': '676',
            'country_code': 'TO'
        },
        {
            'regex': '677',
            'country_code': 'SB'
        },
        {
            'regex': '678',
            'country_code': 'VU'
        },
        {
            'regex': '679',
            'country_code': 'FJ'
        },
        {
            'regex': '680',
            'country_code': 'PW'
        },
        {
            'regex': '681',
            'country_code': 'WF'
        },
        {
            'regex': '682',
            'country_code': 'CK'
        },
        {
            'regex': '683',
            'country_code': 'NU'
        },
        {
            'regex': '685',
            'country_code': 'WS'
        },
        {
            'regex': '686',
            'country_code': 'KI'
        },
        {
            'regex': '687',
            'country_code': 'NC'
        },
        {
            'regex': '688',
            'country_code': 'TV'
        },
        {
            'regex': '689',
            'country_code': 'PF'
        },
        {
            'regex': '690',
            'country_code': 'TK'
        },
        {
            'regex': '691',
            'country_code': 'FM'
        },
        {
            'regex': '692',
            'country_code': 'MH'
        }
    ],
    '7': [
        {
            'regex': '7(840|940)',
            'country_code': 'GE'
        },
        {
            'regex': '7[3489]',
            'country_code': 'RU'
        },
        {
            'regex': '7[67]',
            'country_code': 'KZ'
        }
    ],
    '8': [
        {
            'regex': '81',
            'country_code': 'JP'
        },
        {
            'regex': '82',
            'country_code': 'KR'
        },
        {
            'regex': '84',
            'country_code': 'VN'
        },
        {
            'regex': '850',
            'country_code': 'KP'
        },
        {
            'regex': '852',
            'country_code': 'HK'
        },
        {
            'regex': '853',
            'country_code': 'MO'
        },
        {
            'regex': '855',
            'country_code': 'KH'
        },
        {
            'regex': '856',
            'country_code': 'LA'
        },
        {
            'regex': '86',
            'country_code': 'CN'
        },
        {
            'regex': '880',
            'country_code': 'BD'
        },
        {
            'regex': '886',
            'country_code': 'TW'
        }
    ],
    '9': [
        {
            'regex': '90',
            'country_code': 'TR'
        },
        {
            'regex': '91',
            'country_code': 'IN'
        },
        {
            'regex': '92',
            'country_code': 'PK'
        },
        {
            'regex': '93',
            'country_code': 'AF'
        },
        {
            'regex': '94',
            'country_code': 'LK'
        },
        {
            'regex': '95',
            'country_code': 'MM'
        },
        {
            'regex': '960',
            'country_code': 'MV'
        },
        {
            'regex': '961',
            'country_code': 'LB'
        },
        {
            'regex': '962',
            'country_code': 'JO'
        },
        {
            'regex': '963',
            'country_code': 'SY'
        },
        {
            'regex': '964',
            'country_code': 'IQ'
        },
        {
            'regex': '965',
            'country_code': 'KW'
        },
        {
            'regex': '966',
            'country_code': 'SA'
        },
        {
            'regex': '967',
            'country_code': 'YE'
        },
        {
            'regex': '968',
            'country_code': 'OM'
        },
        {
            'regex': '970',
            'country_code': 'PS'
        },
        {
            'regex': '971',
            'country_code': 'AE'
        },
        {
            'regex': '972',
            'country_code': 'IL'
        },
        {
            'regex': '973',
            'country_code': 'BH'
        },
        {
            'regex': '974',
            'country_code': 'QA'
        },
        {
            'regex': '975',
            'country_code': 'BT'
        },
        {
            'regex': '976',
            'country_code': 'MN'
        },
        {
            'regex': '977',
            'country_code': 'NP'
        },
        {
            'regex': '98',
            'country_code': 'IR'
        },
        {
            'regex': '992',
            'country_code': 'TJ'
        },
        {
            'regex': '993',
            'country_code': 'TM'
        },
        {
            'regex': '994',
            'country_code': 'AZ'
        },
        {
            'regex': '995',
            'country_code': 'GE'
        },
        {
            'regex': '996',
            'country_code': 'KG'
        },
        {
            'regex': '998',
            'country_code': 'UZ'
        }
    ]
}


# The country_code key is included with these exceptions since some cities have
# phone service from more than one country.
#
# The main dict key is the country code, as matched from CALLING_CODE_MAPPING
CALLING_CODE_EXCEPTIONS = {
    'AT': [
        {
            'regex': '435676',
            'country_code': 'AT',
            'name': 'Jungholz',
            'definitive': True
        },
        {
            'regex': '435517',
            'country_code': 'AT',
            'name': 'Mittelberg',
            'definitive': False
        }
    ],
    'CH': [
        {
            'regex': '4152',
            'country_code': 'DE',
            'name': 'Büsingen am Hochrhein',
            'definitive': False
        },
        {
            'regex': '4191',
            'country_code': 'IT',
            'name': "Campione d'Italia",
            'definitive': False
        }
    ],
    'DE': [
        {
            'regex': '494725',
            'country_code': 'DE',
            'name': 'Heligoland',
            'definitive': True
        },
        {
            'regex': '497734',
            'country_code': 'DE',
            'name': 'Büsingen am Hochrhein',
            'definitive': False
        }
    ],
    'ES': [
        {
            'regex': '34(822|828|922|928)',
            'country_code': 'ES',
            'name': 'Canary Islands',
            'definitive': True
        },
        {
            'regex': '34956',
            'country_code': 'ES',
            'name': 'Ceuta',
            'definitive': False
        },
        {
            'regex': '34952',
            'country_code': 'ES',
            'name': 'Melilla',
            'definitive': False
        }
    ],
    'GR': [
        {
            # http://www.mountathosinfos.gr/pages/agionoros/telefonbook.en.html
            # http://www.athosfriends.org/PilgrimsGuide/information/#telephones
            'regex': '3023770(23|41488|41462|22586|24039|94098)',
            'country_code': 'GR',
            'name': 'Mount Athos',
            'definitive': True
        }
    ],
    'IT': [
        {
            'regex': '390342',
            'country_code': 'IT',
            'name': 'Livigno',
            'definitive': False
        }
    ],
    'PT': [
        {
            'regex': '35129[256]',
            'country_code': 'PT',
            'name': 'Azores',
            'definitive': True
        },
        {
            'regex': '351291',
            'country_code': 'PT',
            'name': 'Madeira',
            'definitive': True
        }
    ]
}
