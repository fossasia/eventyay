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


def calculate_rate(country_code, exception_name):
    """
    Calculates the VAT rate for a customer based on their declared country
    and any declared exception information.

    :param country_code:
        The two-character country code where the user resides

    :param exception_name:
        The name of an exception for the country, as returned from
        vat_moss.declared_residence.options()

    :raises:
        ValueError - if country_code is not two characers, or exception_name is not None or a valid exception from options()

    :return:
        A tuple of (Decimal VAT rate, country_code, exception name [or None])
    """

    if not country_code or not isinstance(country_code, str_cls) or len(country_code) != 2:
        raise ValueError('Invalidly formatted country code')

    if exception_name and not isinstance(exception_name, str_cls):
        raise ValueError('Exception name is not None or a string')

    country_code = country_code.upper()

    if country_code not in rates.BY_COUNTRY:
        return (Decimal('0.0'), country_code, None)

    country_info = rates.BY_COUNTRY[country_code]

    if not exception_name:
        return (country_info['rate'], country_code, None)

    if exception_name not in country_info['exceptions']:
        raise ValueError('"%s" is not a valid exception for %s' % (exception_name, country_code))

    rate_info = country_info['exceptions'][exception_name]
    if isinstance(rate_info, Decimal):
        rate = rate_info
    else:
        # This allows handling the complex case of the UK RAF bases in Cyprus
        # that map to the standard country rate. The country code and exception
        # name need to be changed in addition to gettting a special rate.
        rate, country_code, exception_name = rate_info
    return (rate, country_code, exception_name)


def exceptions_by_country(country_code):
    """
    Returns a list of exception names for the given country

    :param country_code:
        The two-character country code for the user

    :raises:
        ValueError - if country_code is not two characers

    :return:
        A list of strings that are VAT exceptions for the country specified
    """

    if not country_code or not isinstance(country_code, str_cls) or len(country_code) != 2:
        raise ValueError('Invalidly formatted country code')

    country_code = country_code.upper()

    return EXCEPTIONS_BY_COUNTRY.get(country_code, [])


def options():
    """
    Return a sorted list of dicts, each containing the keys "name", "code" and
    "exceptions". These should be used to build a user interface for customers
    to declare their country of residence. If their declared country of
    residence includes any exceptions, the user must be presented with an option
    to select their residence as residing in an area with a VAT exception.

    The country codes and names are from ISO 3166-1.

    :return:
        A list of dicts objects each with the keys "name", "code" and
        "exceptions"
    """

    return [
        {
            'name': 'Afghanistan',
            'code': 'AF',
            'exceptions': []
        },
        {
            'name': 'Åland Islands',
            'code': 'AX',
            'exceptions': []
        },
        {
            'name': 'Albania',
            'code': 'AL',
            'exceptions': []
        },
        {
            'name': 'Algeria',
            'code': 'DZ',
            'exceptions': []
        },
        {
            'name': 'American Samoa',
            'code': 'AS',
            'exceptions': []
        },
        {
            'name': 'Andorra',
            'code': 'AD',
            'exceptions': []
        },
        {
            'name': 'Angola',
            'code': 'AO',
            'exceptions': []
        },
        {
            'name': 'Anguilla',
            'code': 'AI',
            'exceptions': []
        },
        {
            'name': 'Antarctica',
            'code': 'AQ',
            'exceptions': []
        },
        {
            'name': 'Antigua and Barbuda',
            'code': 'AG',
            'exceptions': []
        },
        {
            'name': 'Argentina',
            'code': 'AR',
            'exceptions': []
        },
        {
            'name': 'Armenia',
            'code': 'AM',
            'exceptions': []
        },
        {
            'name': 'Aruba',
            'code': 'AW',
            'exceptions': []
        },
        {
            'name': 'Australia',
            'code': 'AU',
            'exceptions': []
        },
        {
            'name': 'Austria',
            'code': 'AT',
            'exceptions': [
                'Jungholz',
                'Mittelberg'
            ]
        },
        {
            'name': 'Azerbaijan',
            'code': 'AZ',
            'exceptions': []
        },
        {
            'name': 'Bahamas',
            'code': 'BS',
            'exceptions': []
        },
        {
            'name': 'Bahrain',
            'code': 'BH',
            'exceptions': []
        },
        {
            'name': 'Bangladesh',
            'code': 'BD',
            'exceptions': []
        },
        {
            'name': 'Barbados',
            'code': 'BB',
            'exceptions': []
        },
        {
            'name': 'Belarus',
            'code': 'BY',
            'exceptions': []
        },
        {
            'name': 'Belgium',
            'code': 'BE',
            'exceptions': []
        },
        {
            'name': 'Belize',
            'code': 'BZ',
            'exceptions': []
        },
        {
            'name': 'Benin',
            'code': 'BJ',
            'exceptions': []
        },
        {
            'name': 'Bermuda',
            'code': 'BM',
            'exceptions': []
        },
        {
            'name': 'Bhutan',
            'code': 'BT',
            'exceptions': []
        },
        {
            'name': 'Bolivia, Plurinational State of',
            'code': 'BO',
            'exceptions': []
        },
        {
            'name': 'Bonaire, Sint Eustatius and Saba',
            'code': 'BQ',
            'exceptions': []
        },
        {
            'name': 'Bosnia and Herzegovina',
            'code': 'BA',
            'exceptions': []
        },
        {
            'name': 'Botswana',
            'code': 'BW',
            'exceptions': []
        },
        {
            'name': 'Bouvet Island',
            'code': 'BV',
            'exceptions': []
        },
        {
            'name': 'Brazil',
            'code': 'BR',
            'exceptions': []
        },
        {
            'name': 'British Indian Ocean Territory',
            'code': 'IO',
            'exceptions': []
        },
        {
            'name': 'Brunei Darussalam',
            'code': 'BN',
            'exceptions': []
        },
        {
            'name': 'Bulgaria',
            'code': 'BG',
            'exceptions': []
        },
        {
            'name': 'Burkina Faso',
            'code': 'BF',
            'exceptions': []
        },
        {
            'name': 'Burundi',
            'code': 'BI',
            'exceptions': []
        },
        {
            'name': 'Cambodia',
            'code': 'KH',
            'exceptions': []
        },
        {
            'name': 'Cameroon',
            'code': 'CM',
            'exceptions': []
        },
        {
            'name': 'Canada',
            'code': 'CA',
            'exceptions': []
        },
        {
            'name': 'Cabo Verde',
            'code': 'CV',
            'exceptions': []
        },
        {
            'name': 'Cayman Islands',
            'code': 'KY',
            'exceptions': []
        },
        {
            'name': 'Central African Republic',
            'code': 'CF',
            'exceptions': []
        },
        {
            'name': 'Chad',
            'code': 'TD',
            'exceptions': []
        },
        {
            'name': 'Chile',
            'code': 'CL',
            'exceptions': []
        },
        {
            'name': 'China',
            'code': 'CN',
            'exceptions': []
        },
        {
            'name': 'Christmas Island',
            'code': 'CX',
            'exceptions': []
        },
        {
            'name': 'Cocos (Keeling) Islands',
            'code': 'CC',
            'exceptions': []
        },
        {
            'name': 'Colombia',
            'code': 'CO',
            'exceptions': []
        },
        {
            'name': 'Comoros',
            'code': 'KM',
            'exceptions': []
        },
        {
            'name': 'Congo',
            'code': 'CG',
            'exceptions': []
        },
        {
            'name': 'Congo, the Democratic Republic of the',
            'code': 'CD',
            'exceptions': []
        },
        {
            'name': 'Cook Islands',
            'code': 'CK',
            'exceptions': []
        },
        {
            'name': 'Costa Rica',
            'code': 'CR',
            'exceptions': []
        },
        {
            'name': "Côte d'Ivoire",
            'code': 'CI',
            'exceptions': []
        },
        {
            'name': 'Croatia',
            'code': 'HR',
            'exceptions': []
        },
        {
            'name': 'Cuba',
            'code': 'CU',
            'exceptions': []
        },
        {
            'name': 'Curaçao',
            'code': 'CW',
            'exceptions': []
        },
        {
            'name': 'Cyprus',
            'code': 'CY',
            'exceptions': []
        },
        {
            'name': 'Czech Republic',
            'code': 'CZ',
            'exceptions': []
        },
        {
            'name': 'Denmark',
            'code': 'DK',
            'exceptions': []
        },
        {
            'name': 'Djibouti',
            'code': 'DJ',
            'exceptions': []
        },
        {
            'name': 'Dominica',
            'code': 'DM',
            'exceptions': []
        },
        {
            'name': 'Dominican Republic',
            'code': 'DO',
            'exceptions': []
        },
        {
            'name': 'Ecuador',
            'code': 'EC',
            'exceptions': []
        },
        {
            'name': 'Egypt',
            'code': 'EG',
            'exceptions': []
        },
        {
            'name': 'El Salvador',
            'code': 'SV',
            'exceptions': []
        },
        {
            'name': 'Equatorial Guinea',
            'code': 'GQ',
            'exceptions': []
        },
        {
            'name': 'Eritrea',
            'code': 'ER',
            'exceptions': []
        },
        {
            'name': 'Estonia',
            'code': 'EE',
            'exceptions': []
        },
        {
            'name': 'Ethiopia',
            'code': 'ET',
            'exceptions': []
        },
        {
            'name': 'Falkland Islands (Malvinas)',
            'code': 'FK',
            'exceptions': []
        },
        {
            'name': 'Faroe Islands',
            'code': 'FO',
            'exceptions': []
        },
        {
            'name': 'Fiji',
            'code': 'FJ',
            'exceptions': []
        },
        {
            'name': 'Finland',
            'code': 'FI',
            'exceptions': []
        },
        {
            'name': 'France',
            'code': 'FR',
            'exceptions': []
        },
        {
            'name': 'French Guiana',
            'code': 'GF',
            'exceptions': []
        },
        {
            'name': 'French Polynesia',
            'code': 'PF',
            'exceptions': []
        },
        {
            'name': 'French Southern Territories',
            'code': 'TF',
            'exceptions': []
        },
        {
            'name': 'Gabon',
            'code': 'GA',
            'exceptions': []
        },
        {
            'name': 'Gambia',
            'code': 'GM',
            'exceptions': []
        },
        {
            'name': 'Georgia',
            'code': 'GE',
            'exceptions': []
        },
        {
            'name': 'Germany',
            'code': 'DE',
            'exceptions': [
                'Büsingen am Hochrhein',
                'Heligoland'
            ]
        },
        {
            'name': 'Ghana',
            'code': 'GH',
            'exceptions': []
        },
        {
            'name': 'Gibraltar',
            'code': 'GI',
            'exceptions': []
        },
        {
            'name': 'Greece',
            'code': 'GR',
            'exceptions': [
                'Mount Athos'
            ]
        },
        {
            'name': 'Greenland',
            'code': 'GL',
            'exceptions': []
        },
        {
            'name': 'Grenada',
            'code': 'GD',
            'exceptions': []
        },
        {
            'name': 'Guadeloupe',
            'code': 'GP',
            'exceptions': []
        },
        {
            'name': 'Guam',
            'code': 'GU',
            'exceptions': []
        },
        {
            'name': 'Guatemala',
            'code': 'GT',
            'exceptions': []
        },
        {
            'name': 'Guernsey',
            'code': 'GG',
            'exceptions': []
        },
        {
            'name': 'Guinea',
            'code': 'GN',
            'exceptions': []
        },
        {
            'name': 'Guinea-Bissau',
            'code': 'GW',
            'exceptions': []
        },
        {
            'name': 'Guyana',
            'code': 'GY',
            'exceptions': []
        },
        {
            'name': 'Haiti',
            'code': 'HT',
            'exceptions': []
        },
        {
            'name': 'Heard Island and McDonald Islands',
            'code': 'HM',
            'exceptions': []
        },
        {
            'name': 'Holy See (Vatican City State)',
            'code': 'VA',
            'exceptions': []
        },
        {
            'name': 'Honduras',
            'code': 'HN',
            'exceptions': []
        },
        {
            'name': 'Hong Kong',
            'code': 'HK',
            'exceptions': []
        },
        {
            'name': 'Hungary',
            'code': 'HU',
            'exceptions': []
        },
        {
            'name': 'Iceland',
            'code': 'IS',
            'exceptions': []
        },
        {
            'name': 'India',
            'code': 'IN',
            'exceptions': []
        },
        {
            'name': 'Indonesia',
            'code': 'ID',
            'exceptions': []
        },
        {
            'name': 'Iran, Islamic Republic of',
            'code': 'IR',
            'exceptions': []
        },
        {
            'name': 'Iraq',
            'code': 'IQ',
            'exceptions': []
        },
        {
            'name': 'Ireland',
            'code': 'IE',
            'exceptions': []
        },
        {
            'name': 'Isle of Man',
            'code': 'IM',
            'exceptions': []
        },
        {
            'name': 'Israel',
            'code': 'IL',
            'exceptions': []
        },
        {
            'name': 'Italy',
            'code': 'IT',
            'exceptions': [
                "Campione d'Italia",
                'Livigno'
            ]
        },
        {
            'name': 'Jamaica',
            'code': 'JM',
            'exceptions': []
        },
        {
            'name': 'Japan',
            'code': 'JP',
            'exceptions': []
        },
        {
            'name': 'Jersey',
            'code': 'JE',
            'exceptions': []
        },
        {
            'name': 'Jordan',
            'code': 'JO',
            'exceptions': []
        },
        {
            'name': 'Kazakhstan',
            'code': 'KZ',
            'exceptions': []
        },
        {
            'name': 'Kenya',
            'code': 'KE',
            'exceptions': []
        },
        {
            'name': 'Kiribati',
            'code': 'KI',
            'exceptions': []
        },
        {
            'name': "Korea, Democratic People's Republic of",
            'code': 'KP',
            'exceptions': []
        },
        {
            'name': 'Korea, Republic of',
            'code': 'KR',
            'exceptions': []
        },
        {
            'name': 'Kosovo, Republic of',
            'code': 'XK',
            'exceptions': []
        },
        {
            'name': 'Kuwait',
            'code': 'KW',
            'exceptions': []
        },
        {
            'name': 'Kyrgyzstan',
            'code': 'KG',
            'exceptions': []
        },
        {
            'name': "Lao People's Democratic Republic",
            'code': 'LA',
            'exceptions': []
        },
        {
            'name': 'Latvia',
            'code': 'LV',
            'exceptions': []
        },
        {
            'name': 'Lebanon',
            'code': 'LB',
            'exceptions': []
        },
        {
            'name': 'Lesotho',
            'code': 'LS',
            'exceptions': []
        },
        {
            'name': 'Liberia',
            'code': 'LR',
            'exceptions': []
        },
        {
            'name': 'Libya',
            'code': 'LY',
            'exceptions': []
        },
        {
            'name': 'Liechtenstein',
            'code': 'LI',
            'exceptions': []
        },
        {
            'name': 'Lithuania',
            'code': 'LT',
            'exceptions': []
        },
        {
            'name': 'Luxembourg',
            'code': 'LU',
            'exceptions': []
        },
        {
            'name': 'Macao',
            'code': 'MO',
            'exceptions': []
        },
        {
            'name': 'Macedonia, the former Yugoslav Republic of',
            'code': 'MK',
            'exceptions': []
        },
        {
            'name': 'Madagascar',
            'code': 'MG',
            'exceptions': []
        },
        {
            'name': 'Malawi',
            'code': 'MW',
            'exceptions': []
        },
        {
            'name': 'Malaysia',
            'code': 'MY',
            'exceptions': []
        },
        {
            'name': 'Maldives',
            'code': 'MV',
            'exceptions': []
        },
        {
            'name': 'Mali',
            'code': 'ML',
            'exceptions': []
        },
        {
            'name': 'Malta',
            'code': 'MT',
            'exceptions': []
        },
        {
            'name': 'Marshall Islands',
            'code': 'MH',
            'exceptions': []
        },
        {
            'name': 'Martinique',
            'code': 'MQ',
            'exceptions': []
        },
        {
            'name': 'Mauritania',
            'code': 'MR',
            'exceptions': []
        },
        {
            'name': 'Mauritius',
            'code': 'MU',
            'exceptions': []
        },
        {
            'name': 'Mayotte',
            'code': 'YT',
            'exceptions': []
        },
        {
            'name': 'Mexico',
            'code': 'MX',
            'exceptions': []
        },
        {
            'name': 'Micronesia, Federated States of',
            'code': 'FM',
            'exceptions': []
        },
        {
            'name': 'Moldova, Republic of',
            'code': 'MD',
            'exceptions': []
        },
        {
            'name': 'Monaco',
            'code': 'MC',
            'exceptions': []
        },
        {
            'name': 'Mongolia',
            'code': 'MN',
            'exceptions': []
        },
        {
            'name': 'Montenegro',
            'code': 'ME',
            'exceptions': []
        },
        {
            'name': 'Montserrat',
            'code': 'MS',
            'exceptions': []
        },
        {
            'name': 'Morocco',
            'code': 'MA',
            'exceptions': []
        },
        {
            'name': 'Mozambique',
            'code': 'MZ',
            'exceptions': []
        },
        {
            'name': 'Myanmar',
            'code': 'MM',
            'exceptions': []
        },
        {
            'name': 'Namibia',
            'code': 'NA',
            'exceptions': []
        },
        {
            'name': 'Nauru',
            'code': 'NR',
            'exceptions': []
        },
        {
            'name': 'Nepal',
            'code': 'NP',
            'exceptions': []
        },
        {
            'name': 'Netherlands',
            'code': 'NL',
            'exceptions': []
        },
        {
            'name': 'New Caledonia',
            'code': 'NC',
            'exceptions': []
        },
        {
            'name': 'New Zealand',
            'code': 'NZ',
            'exceptions': []
        },
        {
            'name': 'Nicaragua',
            'code': 'NI',
            'exceptions': []
        },
        {
            'name': 'Niger',
            'code': 'NE',
            'exceptions': []
        },
        {
            'name': 'Nigeria',
            'code': 'NG',
            'exceptions': []
        },
        {
            'name': 'Niue',
            'code': 'NU',
            'exceptions': []
        },
        {
            'name': 'Norfolk Island',
            'code': 'NF',
            'exceptions': []
        },
        {
            'name': 'Northern Mariana Islands',
            'code': 'MP',
            'exceptions': []
        },
        {
            'name': 'Norway',
            'code': 'NO',
            'exceptions': []
        },
        {
            'name': 'Oman',
            'code': 'OM',
            'exceptions': []
        },
        {
            'name': 'Pakistan',
            'code': 'PK',
            'exceptions': []
        },
        {
            'name': 'Palau',
            'code': 'PW',
            'exceptions': []
        },
        {
            'name': 'Palestine, State of',
            'code': 'PS',
            'exceptions': []
        },
        {
            'name': 'Panama',
            'code': 'PA',
            'exceptions': []
        },
        {
            'name': 'Papua New Guinea',
            'code': 'PG',
            'exceptions': []
        },
        {
            'name': 'Paraguay',
            'code': 'PY',
            'exceptions': []
        },
        {
            'name': 'Peru',
            'code': 'PE',
            'exceptions': []
        },
        {
            'name': 'Philippines',
            'code': 'PH',
            'exceptions': []
        },
        {
            'name': 'Pitcairn',
            'code': 'PN',
            'exceptions': []
        },
        {
            'name': 'Poland',
            'code': 'PL',
            'exceptions': []
        },
        {
            'name': 'Portugal',
            'code': 'PT',
            'exceptions': [
                'Azores',
                'Madeira'
            ]
        },
        {
            'name': 'Puerto Rico',
            'code': 'PR',
            'exceptions': []
        },
        {
            'name': 'Qatar',
            'code': 'QA',
            'exceptions': []
        },
        {
            'name': 'Réunion',
            'code': 'RE',
            'exceptions': []
        },
        {
            'name': 'Romania',
            'code': 'RO',
            'exceptions': []
        },
        {
            'name': 'Russian Federation',
            'code': 'RU',
            'exceptions': []
        },
        {
            'name': 'Rwanda',
            'code': 'RW',
            'exceptions': []
        },
        {
            'name': 'Saint Barthélemy',
            'code': 'BL',
            'exceptions': []
        },
        {
            'name': 'Saint Helena, Ascension and Tristan da Cunha',
            'code': 'SH',
            'exceptions': []
        },
        {
            'name': 'Saint Kitts and Nevis',
            'code': 'KN',
            'exceptions': []
        },
        {
            'name': 'Saint Lucia',
            'code': 'LC',
            'exceptions': []
        },
        {
            'name': 'Saint Martin (French part)',
            'code': 'MF',
            'exceptions': []
        },
        {
            'name': 'Saint Pierre and Miquelon',
            'code': 'PM',
            'exceptions': []
        },
        {
            'name': 'Saint Vincent and the Grenadines',
            'code': 'VC',
            'exceptions': []
        },
        {
            'name': 'Samoa',
            'code': 'WS',
            'exceptions': []
        },
        {
            'name': 'San Marino',
            'code': 'SM',
            'exceptions': []
        },
        {
            'name': 'Sao Tome and Principe',
            'code': 'ST',
            'exceptions': []
        },
        {
            'name': 'Saudi Arabia',
            'code': 'SA',
            'exceptions': []
        },
        {
            'name': 'Senegal',
            'code': 'SN',
            'exceptions': []
        },
        {
            'name': 'Serbia',
            'code': 'RS',
            'exceptions': []
        },
        {
            'name': 'Seychelles',
            'code': 'SC',
            'exceptions': []
        },
        {
            'name': 'Sierra Leone',
            'code': 'SL',
            'exceptions': []
        },
        {
            'name': 'Singapore',
            'code': 'SG',
            'exceptions': []
        },
        {
            'name': 'Sint Maarten (Dutch part)',
            'code': 'SX',
            'exceptions': []
        },
        {
            'name': 'Slovakia',
            'code': 'SK',
            'exceptions': []
        },
        {
            'name': 'Slovenia',
            'code': 'SI',
            'exceptions': []
        },
        {
            'name': 'Solomon Islands',
            'code': 'SB',
            'exceptions': []
        },
        {
            'name': 'Somalia',
            'code': 'SO',
            'exceptions': []
        },
        {
            'name': 'South Africa',
            'code': 'ZA',
            'exceptions': []
        },
        {
            'name': 'South Georgia and the South Sandwich Islands',
            'code': 'GS',
            'exceptions': []
        },
        {
            'name': 'South Sudan',
            'code': 'SS',
            'exceptions': []
        },
        {
            'name': 'Spain',
            'code': 'ES',
            'exceptions': [
                'Canary Islands',
                'Ceuta',
                'Melilla'
            ]
        },
        {
            'name': 'Sri Lanka',
            'code': 'LK',
            'exceptions': []
        },
        {
            'name': 'Sudan',
            'code': 'SD',
            'exceptions': []
        },
        {
            'name': 'Suriname',
            'code': 'SR',
            'exceptions': []
        },
        {
            'name': 'Svalbard and Jan Mayen',
            'code': 'SJ',
            'exceptions': []
        },
        {
            'name': 'Swaziland',
            'code': 'SZ',
            'exceptions': []
        },
        {
            'name': 'Sweden',
            'code': 'SE',
            'exceptions': []
        },
        {
            'name': 'Switzerland',
            'code': 'CH',
            'exceptions': []
        },
        {
            'name': 'Syrian Arab Republic',
            'code': 'SY',
            'exceptions': []
        },
        {
            'name': 'Taiwan, Province of China',
            'code': 'TW',
            'exceptions': []
        },
        {
            'name': 'Tajikistan',
            'code': 'TJ',
            'exceptions': []
        },
        {
            'name': 'Tanzania, United Republic of',
            'code': 'TZ',
            'exceptions': []
        },
        {
            'name': 'Thailand',
            'code': 'TH',
            'exceptions': []
        },
        {
            'name': 'Timor-Leste',
            'code': 'TL',
            'exceptions': []
        },
        {
            'name': 'Togo',
            'code': 'TG',
            'exceptions': []
        },
        {
            'name': 'Tokelau',
            'code': 'TK',
            'exceptions': []
        },
        {
            'name': 'Tonga',
            'code': 'TO',
            'exceptions': []
        },
        {
            'name': 'Trinidad and Tobago',
            'code': 'TT',
            'exceptions': []
        },
        {
            'name': 'Tunisia',
            'code': 'TN',
            'exceptions': []
        },
        {
            'name': 'Turkey',
            'code': 'TR',
            'exceptions': []
        },
        {
            'name': 'Turkmenistan',
            'code': 'TM',
            'exceptions': []
        },
        {
            'name': 'Turks and Caicos Islands',
            'code': 'TC',
            'exceptions': []
        },
        {
            'name': 'Tuvalu',
            'code': 'TV',
            'exceptions': []
        },
        {
            'name': 'Uganda',
            'code': 'UG',
            'exceptions': []
        },
        {
            'name': 'Ukraine',
            'code': 'UA',
            'exceptions': []
        },
        {
            'name': 'United Arab Emirates',
            'code': 'AE',
            'exceptions': []
        },
        {
            'name': 'United Kingdom',
            'code': 'GB',
            'exceptions': [
                'Akrotiri',
                'Dhekelia'
            ]
        },
        {
            'name': 'United States',
            'code': 'US',
            'exceptions': []
        },
        {
            'name': 'United States Minor Outlying Islands',
            'code': 'UM',
            'exceptions': []
        },
        {
            'name': 'Uruguay',
            'code': 'UY',
            'exceptions': []
        },
        {
            'name': 'Uzbekistan',
            'code': 'UZ',
            'exceptions': []
        },
        {
            'name': 'Vanuatu',
            'code': 'VU',
            'exceptions': []
        },
        {
            'name': 'Venezuela, Bolivarian Republic of',
            'code': 'VE',
            'exceptions': []
        },
        {
            'name': 'Viet Nam',
            'code': 'VN',
            'exceptions': []
        },
        {
            'name': 'Virgin Islands, British',
            'code': 'VG',
            'exceptions': []
        },
        {
            'name': 'Virgin Islands, U.S.',
            'code': 'VI',
            'exceptions': []
        },
        {
            'name': 'Wallis and Futuna',
            'code': 'WF',
            'exceptions': []
        },
        {
            'name': 'Western Sahara',
            'code': 'EH',
            'exceptions': []
        },
        {
            'name': 'Yemen',
            'code': 'YE',
            'exceptions': []
        },
        {
            'name': 'Zambia',
            'code': 'ZM',
            'exceptions': []
        },
        {
            'name': 'Zimbabwe',
            'code': 'ZW',
            'exceptions': []
        }
    ]


# The valid exception names, listed by country
EXCEPTIONS_BY_COUNTRY = {
    'AT': ['Jungholz', 'Mittelberg'],
    'DE': ['Büsingen am Hochrhein', 'Heligoland'],
    'ES': ['Canary Islands', 'Ceuta', 'Melilla'],
    'GB': ['Akrotiri', 'Dhekelia'],
    'GR': ['Mount Athos'],
    'IT': ["Campione d'Italia", 'Livigno'],
    'PT': ['Azores', 'Madeira']
}
