import re
import pycountry
from .item_type import ItemType
from .party import Party
from .registries import ViesRegistry
from .result import VatNumberCheckResult
from .vat_charge import VatCharge, VatChargeAction
from .vat_rules import VAT_RULES


__version__ = '1.3.18'


WHITESPACE_EXPRESSION = re.compile(r'[\s\-]+')
"""Whitespace expression.

Used for cleaning VAT numbers.
"""


VAT_NUMBER_EXPRESSIONS = {
    'AT': re.compile(r'^U\d{8}$', re.IGNORECASE),
    'BE': re.compile(r'^\d{9,10}$'),
    'BG': re.compile(r'^\d{9,10}$'),
    'CY': re.compile(r'^\d{8}[a-z]$', re.IGNORECASE),
    'CZ': re.compile(r'^\d{8,10}$'),
    'DE': re.compile(r'^\d{9}$'),
    'DK': re.compile(r'^\d{8}$'),
    'EE': re.compile(r'^\d{9}$'),
    'ES': re.compile(r'^[\da-z]\d{7}[\da-z]$', re.IGNORECASE),
    'FI': re.compile(r'^\d{8}$'),
    'FR': re.compile(r'^[\da-hj-np-z]{2}\d{9}$', re.IGNORECASE),
    'GR': re.compile(r'^\d{9}$'),
    'HR': re.compile(r'^\d{11}$'),
    'HU': re.compile(r'^\d{8}$'),
    'IE': re.compile(r'^((\d{7}[a-z])|(\d[a-z]\d{5}[a-z])|(\d{6,7}[a-z]{2}))$',
                     re.IGNORECASE),
    'IT': re.compile(r'^\d{11}$'),
    'LT': re.compile(r'^((\d{9})|(\d{12}))$'),
    'LU': re.compile(r'^\d{8}$'),
    'LV': re.compile(r'^\d{11}$'),
    'MT': re.compile(r'^\d{8}$'),
    'NL': re.compile(r'^\d{9}B\d{2}$', re.IGNORECASE),
    'PL': re.compile(r'^\d{10}$'),
    'PT': re.compile(r'^\d{9}$'),
    'RO': re.compile(r'^\d{2,10}$'),
    'SE': re.compile(r'^\d{12}$'),
    'SI': re.compile(r'^\d{8}$'),
    'SK': re.compile(r'^\d{10}$'),
}
"""VAT number expressions.

Mapping form ISO 3166-1-alpha-2 country codes to the whitespace-less expression
a valid VAT number from the given country must match excluding the country code
prefix.

EU VAT number structures are retrieved from `VIES
<http://ec.europa.eu/taxation_customs/vies/faqvies.do>`_.
"""


VIES_REGISTRY = ViesRegistry()
"""VIES registry instance.
"""


VAT_REGISTRIES = {
    'AT': VIES_REGISTRY,
    'BE': VIES_REGISTRY,
    'BG': VIES_REGISTRY,
    'CY': VIES_REGISTRY,
    'CZ': VIES_REGISTRY,
    'DE': VIES_REGISTRY,
    'DK': VIES_REGISTRY,
    'EE': VIES_REGISTRY,
    'ES': VIES_REGISTRY,
    'FI': VIES_REGISTRY,
    'FR': VIES_REGISTRY,
    'GR': VIES_REGISTRY,
    'HU': VIES_REGISTRY,
    'HR': VIES_REGISTRY,
    'IE': VIES_REGISTRY,
    'IT': VIES_REGISTRY,
    'LT': VIES_REGISTRY,
    'LU': VIES_REGISTRY,
    'LV': VIES_REGISTRY,
    'MT': VIES_REGISTRY,
    'NL': VIES_REGISTRY,
    'PL': VIES_REGISTRY,
    'PT': VIES_REGISTRY,
    'RO': VIES_REGISTRY,
    'SE': VIES_REGISTRY,
    'SK': VIES_REGISTRY,
    'SI': VIES_REGISTRY,
}
"""VAT registries.

Mapping from ISO 3166-1-alpha-2 country codes to the VAT registry capable of
validating the VAT number.
"""


def decompose_vat_number(vat_number, country_code=None):
    """Decompose a VAT number and an optional country code.

    :param vat_number: VAT number.
    :param country_code:
        Optional country code. Default ``None`` prompting detection from the
        VAT number.
    :returns:
        a :class:`tuple` containing the VAT number and country code or
        ``(vat_number, None)`` if decomposition failed.
    """

    # Clean the VAT number.
    vat_number = WHITESPACE_EXPRESSION.sub('', vat_number).upper()

    # Attempt to determine the country code of the VAT number if possible.
    if not country_code:
        country_code = vat_number[0:2]

        if any(c.isdigit() for c in country_code):
            # Country code should not contain digits
            return (vat_number, None)

        # Non-ISO code used for Greece.
        if country_code == 'EL':
            country_code = 'GR'

        if country_code not in VAT_REGISTRIES:
            try:
                if not pycountry.countries.get(alpha_2=country_code):
                    return (vat_number, None)
            except KeyError:
                # country code not found
                return (vat_number, None)
        vat_number = vat_number[2:]
    elif vat_number[0:2] == country_code:
        vat_number = vat_number[2:]
    elif country_code == 'GR' and vat_number[0:2] == 'EL':
        vat_number = vat_number[2:]

    return vat_number, country_code


def is_vat_number_format_valid(vat_number, country_code=None):
    """Test if the format of a VAT number is valid.

    :param vat_number: VAT number to validate.
    :param country_code:
        Optional country code. Should be supplied if known, as there is no
        guarantee that naively entered VAT numbers contain the correct alpha-2
        country code prefix for EU countries just as not all non-EU countries
        have a reliable country code prefix. Default ``None`` prompting
        detection.
    :returns:
        ``True`` if the format of the VAT number can be fully asserted as valid
        or ``False`` if not.
    """

    vat_number, country_code = decompose_vat_number(vat_number, country_code)

    if not vat_number or not country_code:
        return False
    elif not any(c.isdigit() for c in vat_number):
        return False
    elif country_code not in VAT_NUMBER_EXPRESSIONS:
        return False
    elif not VAT_NUMBER_EXPRESSIONS[country_code].match(vat_number):
        return False

    return True


def check_vat_number(vat_number, country_code=None):
    """Check if a VAT number is valid.

    If possible, the VAT number will be checked against available registries.

    :param vat_number: VAT number to validate.
    :param country_code:
        Optional country code. Should be supplied if known, as there is no
        guarantee that naively entered VAT numbers contain the correct alpha-2
        country code prefix for EU countries just as not all non-EU countries
        have a reliable country code prefix. Default ``None`` prompting
        detection.
    :returns:
        a :class:`VatNumberCheckResult` instance containing the result for
        the full VAT number check.
    """

    # Decompose the VAT number.
    vat_number, country_code = decompose_vat_number(vat_number, country_code)
    if not vat_number or not country_code:
        return VatNumberCheckResult(False, [
            '> Unable to decompose VAT number, resulted in %r and %r' %
            (vat_number, country_code)
        ])

    # Test the VAT number format.
    format_result = is_vat_number_format_valid(vat_number, country_code)
    if format_result is not True:
        return VatNumberCheckResult(format_result, [
            '> VAT number validation failed: %r' % (format_result)
        ])

    # Attempt to check the VAT number against a registry.
    if country_code not in VAT_REGISTRIES:
        return VatNumberCheckResult()

    return VAT_REGISTRIES[country_code].check_vat_number(vat_number,
                                                         country_code)


def get_sale_vat_charge(date,
                        item_type,
                        buyer,
                        seller):
    """Get the VAT charge for performing the sale of an item.

    Currently only supports determination of the VAT charge for
    telecommunications, broadcasting and electronic services in the EU.

    :param date: Sale date.
    :type date: datetime.date
    :param item_type: Type of the item being sold.
    :type item_type: ItemType
    :param buyer: Buyer.
    :type buyer: Party
    :param seller: Seller.
    :type seller: Party
    :rtype: VatCharge
    """

    # Only telecommunications, broadcasting and electronic services are
    # currently supported.
    if not item_type.is_electronic_service and \
       not item_type.is_telecommunications_service and \
       not item_type.is_broadcasting_service:
        raise NotImplementedError(
            'VAT charge determination for items that are not '
            'telecommunications, broadcasting or electronic services is '
            'currently not supported'
        )

    # Determine the rules for the countries in which the buyer and seller
    # reside.
    buyer_vat_rules = VAT_RULES.get(buyer.country_code, None)
    seller_vat_rules = VAT_RULES.get(seller.country_code, None)

    # Test if the country to which the item is being sold enforces specific
    # VAT rules for selling to the given country.
    if buyer_vat_rules:
        try:
            return buyer_vat_rules.get_sale_to_country_vat_charge(date,
                                                                  item_type,
                                                                  buyer,
                                                                  seller)
        except NotImplementedError:
            pass

    # Fall back to applying VAT rules for selling from the seller's country.
    if seller_vat_rules:
        try:
            return seller_vat_rules.get_sale_from_country_vat_charge(date,
                                                                     item_type,
                                                                     buyer,
                                                                     seller)
        except NotImplementedError:
            pass

    # Nothing we can do from here.
    raise NotImplementedError(
        'cannot determine VAT charge for a sale of item %r between %r and %r' %
        (item_type, seller, buyer)
    )


__all__ = (
    'check_vat_number',
    'get_sale_vat_charge',
    'is_vat_number_format_valid',
    ItemType.__name__,
    Party.__name__,
    VatCharge.__name__,
    VatChargeAction.__name__,
)
