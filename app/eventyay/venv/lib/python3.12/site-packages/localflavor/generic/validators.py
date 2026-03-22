import re
import string

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _
from stdnum import ean, iban

from .countries.iso_3166 import ISO_3166_1_ALPHA2_COUNTRY_CODES

# Dictionary of ISO country code to IBAN length.
#
# The official IBAN Registry document is the best source for up-to-date information about IBAN formats and which
# countries are in IBAN.
#
# https://www.swift.com/standards/data-standards/iban
#
# The IBAN_COUNTRY_CODE_LENGTH dictionary has been updated version 94 of the IBAN Registry document which was published
# in April 2023.
#
# Other Resources:
#
# https://en.wikipedia.org/wiki/International_Bank_Account_Number#IBAN_formats_by_country
# http://www.ecbs.org/iban/france-bank-account-number.html
# https://www.nordea.com/V%C3%A5ra+tj%C3%A4nster/Internationella+produkter+och+tj%C3%A4nster/Cash+Management/IBAN+countries/908472.html


IBAN_COUNTRY_CODE_LENGTH = {'AD': 24,  # Andorra
                            'AE': 23,  # United Arab Emirates
                            'AL': 28,  # Albania
                            'AT': 20,  # Austria
                            'AZ': 28,  # Azerbaijan
                            'BA': 20,  # Bosnia and Herzegovina
                            'BE': 16,  # Belgium
                            'BG': 22,  # Bulgaria
                            'BH': 22,  # Bahrain
                            'BI': 27,  # Burundi
                            'BR': 29,  # Brazil
                            'BY': 28,  # Republic of Belarus
                            'CH': 21,  # Switzerland
                            'CR': 22,  # Costa Rica
                            'CY': 28,  # Cyprus
                            'CZ': 24,  # Czech Republic
                            'DE': 22,  # Germany
                            'DJ': 27,  # Djibouti
                            'DK': 18,  # Denmark
                            'DO': 28,  # Dominican Republic
                            'EE': 20,  # Estonia
                            'EG': 29,  # Egypt
                            'ES': 24,  # Spain
                            'FI': 18,  # Finland
                            'FO': 18,  # Faroe Islands
                            'FR': 27,  # France + French Guiana (GF), Guadeloupe (GP), Martinique (MQ), Réunion (RE),
                                       #          French Polynesia (PF), French Southern Territories (TF), Mayotte (YT),
                                       #          New Caledonia (NC), Saint Barthélemy (BL),
                                       #          Saint Martin - French part (MF), Saint-Pierre and Miquelon (PM),
                                       #          Wallis and Futuna (WF)
                            'GB': 22,  # United Kingdom + Guernsey (GG), Isle of Man (IM), Jersey (JE)
                            'GE': 22,  # Georgia
                            'GI': 23,  # Gibraltar
                            'GL': 18,  # Greenland
                            'GR': 27,  # Greece
                            'GT': 28,  # Guatemala
                            'HR': 21,  # Croatia
                            'HU': 28,  # Hungary
                            'IE': 22,  # Ireland
                            'IL': 23,  # Israel
                            'IQ': 23,  # Iraq
                            'IS': 26,  # Iceland
                            'IT': 27,  # Italy
                            'JO': 30,  # Jordan
                            'KW': 30,  # Kuwait
                            'KZ': 20,  # Kazakhstan
                            'LB': 28,  # Lebanon
                            'LC': 32,  # Saint Lucia
                            'LI': 21,  # Liechtenstein
                            'LT': 20,  # Lithuania
                            'LU': 20,  # Luxembourg
                            'LV': 21,  # Latvia
                            'LY': 25,  # Libya
                            'MC': 27,  # Monaco
                            'MD': 24,  # Moldova
                            'ME': 22,  # Montenegro
                            'MK': 19,  # Macedonia
                            'MN': 20,  # Mongolia
                            'MR': 27,  # Mauritania
                            'MT': 31,  # Malta
                            'MU': 30,  # Mauritius
                            'NI': 28,  # Nicaragua
                            'NL': 18,  # Netherlands
                            'NO': 15,  # Norway
                            'PK': 24,  # Pakistan
                            'PL': 28,  # Poland
                            'PS': 29,  # Palestine
                            'PT': 25,  # Portugal
                            'QA': 29,  # Qatar
                            'RO': 24,  # Romania
                            'RS': 22,  # Serbia
                            'RU': 33,  # Russia
                            'SA': 24,  # Saudi Arabia
                            'SC': 31,  # Seychelles
                            'SD': 18,  # Sudan
                            'SE': 24,  # Sweden
                            'SI': 19,  # Slovenia
                            'SK': 24,  # Slovakia
                            'SM': 27,  # San Marino
                            'ST': 25,  # Sao Tome and Principe
                            'SV': 28,  # El Salvador
                            'TL': 23,  # Timor-Leste
                            'TN': 24,  # Tunisia
                            'TR': 26,  # Turkey
                            'UA': 29,  # Ukraine
                            'VA': 22,  # Vatican City State
                            'VG': 24,  # British Virgin Islands
                            'XK': 20}  # Kosovo (user-assigned country code)


# Nordea has catalogued IBANs for some additional countries but they are not part of the office IBAN network yet.
#
# Reference:
# https://www.nordea.com/V%C3%A5ra+tj%C3%A4nster/Internationella+produkter+och+tj%C3%A4nster/Cash+Management/IBAN+countries/908472.html

NORDEA_COUNTRY_CODE_LENGTH = {'AO': 25,  # Angola
                              'BJ': 28,  # Benin
                              'BF': 27,  # Burkina Faso
                              'CI': 28,  # Ivory Coast
                              'CG': 27,  # Congo
                              'CM': 27,  # Cameroon
                              'CV': 25,  # Cape Verde
                              'DZ': 24,  # Algeria
                              'GA': 27,  # Gabon
                              'IR': 26,  # Iran
                              'MG': 27,  # Madagascar
                              'ML': 28,  # Mali
                              'MZ': 25,  # Mozambique
                              'SN': 28}  # Senegal


@deconstructible
class IBANValidator:
    """A validator for International Bank Account Numbers (IBAN - ISO 13616-1:2007)."""

    def __init__(self, use_nordea_extensions=False, include_countries=None):
        self.use_nordea_extensions = use_nordea_extensions
        self.include_countries = include_countries

        self.validation_countries = IBAN_COUNTRY_CODE_LENGTH.copy()
        if self.use_nordea_extensions:
            self.validation_countries.update(NORDEA_COUNTRY_CODE_LENGTH)

        if self.include_countries:
            for country_code in self.include_countries:
                if country_code not in self.validation_countries:
                    msg = 'Explicitly requested country code %s is not ' \
                          'part of the configured IBAN validation set.' % country_code
                    raise ImproperlyConfigured(msg)

    def __eq__(self, other):
        return (self.use_nordea_extensions == other.use_nordea_extensions and
                self.include_countries == other.include_countries)

    @staticmethod
    def iban_checksum(value):
        """
        Returns check digits for an input IBAN number.

        Original checksum in input value is ignored.
        """
        # 1. Move the two initial characters to the end of the string, replacing checksum for '00'
        value = value[4:] + value[:2] + '00'

        # 2. Replace each letter in the string with two digits, thereby expanding the string, where
        #    A = 10, B = 11, ..., Z = 35.
        value_digits = ''
        for x in value:
            if '0' <= x <= '9':
                value_digits += x
            elif 'A' <= x <= 'Z':
                value_digits += str(ord(x) - 55)
            else:
                raise ValidationError(
                    _('%(character)s is not a valid character for IBAN.'),
                    code='invalid',
                    params={'character': x})

        # 3. The remainder of the number above when divided by 97 is then subtracted from 98.
        return '%02d' % (98 - int(value_digits) % 97)

    def __call__(self, value):
        """
        Validates the IBAN value using the official IBAN validation algorithm.

        https://en.wikipedia.org/wiki/International_Bank_Account_Number#Validating_the_IBAN
        """
        if value is None:
            return

        value = value.upper().replace(' ', '').replace('-', '')

        # Check that the total IBAN length is correct as per the country. If not, the IBAN is invalid.
        country_code = value[:2]
        if country_code in self.validation_countries:

            if self.validation_countries[country_code] != len(value):
                raise ValidationError(
                    _('%(country_code)s IBANs must contain %(number)s characters.'),
                    code='invalid',
                    params={'country_code': country_code, 'number': self.validation_countries[country_code]},
                )

        else:
            raise ValidationError(
                _('%(country_code)s is not a valid country code for IBAN.'),
                code='invalid',
                params={'country_code': country_code},
            )
        if self.include_countries and country_code not in self.include_countries:
            raise ValidationError(
                _('%(country_code)s IBANs are not allowed in this field.'),
                code='invalid',
                params={'country_code': country_code},
            )

        if self.iban_checksum(value) != value[2:4]:
            raise ValidationError(_('Not a valid IBAN.'), code='invalid')

        # stdnum.iban checks the BBAN as well so we do a final check. stdnum doesn't include the Nordea extensions which
        # is why we only run the stdnum check for regular IBANs.
        # Care needs to be taken to keep supporting the Nordea IBANs when we replace more of this code with stdnum.iban.
        if country_code not in NORDEA_COUNTRY_CODE_LENGTH and not iban.is_valid(value):
            raise ValidationError(_('Not a valid IBAN.'), code='invalid')


@deconstructible
class BICValidator:
    """
    A validator for SWIFT Business Identifier Codes (ISO 9362:2009).

    Validation is based on the BIC structure found on wikipedia.

    https://en.wikipedia.org/wiki/ISO_9362#Structure
    """

    def __eq__(self, other):
        # There is no outside modification of properties so this should always be true by default.
        return True

    def __call__(self, value):
        if value is None:
            return

        value = value.upper()

        # Length is 8 or 11.
        bic_length = len(value)
        if bic_length not in (8, 11):
            raise ValidationError(_('BIC codes have either 8 or 11 characters.'), code='invalid')

        # BIC is alphanumeric
        if any(char not in string.ascii_uppercase + string.digits for char in value):
            raise ValidationError(_('BIC codes only contain alphabet letters and digits.'), code='invalid')

        # First 4 letters are A - Z.
        institution_code = value[:4]
        if any(char not in string.ascii_uppercase for char in institution_code):
            raise ValidationError(
                _('%(institution_code)s is not a valid institution code.'),
                code='invalid',
                params={'institution_code': institution_code},
            )

        # Letters 5 and 6 consist of an ISO 3166-1 alpha-2 country code.
        country_code = value[4:6]
        if country_code not in ISO_3166_1_ALPHA2_COUNTRY_CODES:
            raise ValidationError(
                _('%(country_code)s is not a valid country code.'),
                code='invalid',
                params={'country_code': country_code},
            )

        # Letters 7 and 8 are a "location" code. As per ISO20022 Payments
        # Maintenance 2009 document, they may only be from the charset [A-Z2-9][A-NP-Z0-9]
        if value[6] == '1' or value[7] == 'O':
            raise ValidationError(
                _('%(location_code)s is not a valid location code.'),
                code='invalid',
                params={'location_code': value[6:8]},
            )


@deconstructible
class EANValidator:
    """
    A generic validator for EAN like codes with the last digit being the checksum.

    http://en.wikipedia.org/wiki/International_Article_Number_(EAN)
    """

    message = _('Not a valid EAN code.')

    def __init__(self, strip_nondigits=False, message=None):
        if message is not None:
            self.message = message
        self.strip_nondigits = strip_nondigits

    def __eq__(self, other):
        return ((not hasattr(self, 'message') or self.message == other.message) and
                self.strip_nondigits == other.strip_nondigits)

    def __call__(self, value):
        if value is None:
            return
        if self.strip_nondigits:
            value = re.compile(r'[^\d]+').sub('', value)
        if not ean.is_valid(value):
            raise ValidationError(self.message, code='invalid')


VATIN_PATTERN_MAP = {
    'AT': r'^ATU\d{8}$',
    'BE': r'^BE0?\d{9}$',
    'BG': r'^BG\d{9,10}$',
    'HR': r'^HR\d{11}$',
    'CY': r'^CY\d{8}[A-Z]$',
    'CZ': r'^CZ\d{8,10}$',
    'DE': r'^DE\d{9}$',
    'DK': r'^DK\d{8}$',
    'EE': r'^EE\d{9}$',
    'EL': r'^EL\d{9}$',
    'ES': r'^ES[A-Z0-9]\d{7}[A-Z0-9]$',
    'FI': r'^FI\d{8}$',
    'FR': r'^FR[A-HJ-NP-Z0-9][A-HJ-NP-Z0-9]\d{9}$',
    'GB': r'^(GB(GD|HA)\d{3}|GB\d{9}|GB\d{12})$',
    'HU': r'^HU\d{8}$',
    'IE': r'^IE\d[A-Z0-9\+\*]\d{5}[A-Z]{1,2}$',
    'IT': r'^IT\d{11}$',
    'LT': r'^LT(\d{9}|\d{12})$',
    'LU': r'^LU\d{8}$',
    'LV': r'^LV\d{11}$',
    'MT': r'^MT\d{8}$',
    'NL': r'^NL\d{9}B\d{2}$',
    'PL': r'^PL\d{10}$',
    'PT': r'^PT\d{9}$',
    'RO': r'^RO\d{2,10}$',
    'SE': r'^SE\d{10}01$',
    'SI': r'^SI\d{8}$',
    'SK': r'^SK\d{10}$',
}
"""
Map of country codes and regular expressions.

See https://en.wikipedia.org/wiki/VAT_identification_number
"""

VATIN_COUNTRY_CODE_LENGTH = 2
"""
Length of the country code prefix of a VAT identification number.

Codes are two letter ISO 3166-1 alpha-2 codes except for Greece that uses
ISO 639-1.
"""


@deconstructible
class VATINValidator:
    """
    A validator for VAT identification numbers.

    Currently only supports European VIES VAT identification numbers.

    See See https://en.wikipedia.org/wiki/VAT_identification_number
    """
    messages = {
        'country_code': _('%(country_code)s is not a valid country code.'),
        'vatin': _('%(vatin)s is not a valid VAT identification number.'),
    }

    def __call__(self, value):
        country_code, number = self.clean(value)
        try:
            match = re.match(VATIN_PATTERN_MAP[country_code], value)
            if not match:
                raise ValidationError(
                    self.messages['vatin'],
                    code='vatin',
                    params={'vatin': value}
                )

        except KeyError:
            raise ValidationError(
                self.messages['country_code'],
                code='country_code',
                params={'country_code': country_code}
            )

    def clean(self, value):
        """Return tuple of country code and number."""
        return value[:VATIN_COUNTRY_CODE_LENGTH], value[VATIN_COUNTRY_CODE_LENGTH:]
