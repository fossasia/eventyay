import datetime
from decimal import Decimal
from .countries import EU_COUNTRY_CODES
from .item_type import ItemType
from .vat_charge import VatCharge, VatChargeAction
from .utils import ensure_decimal

JANUARY_1_2015 = datetime.date(2015, 1, 1)


class VatRules(object):
    """Base VAT rules for a country.
    """

    def get_vat_rate(self, item_type):
        """Get the VAT rate for an item type.

        :param item_type: Item type.
        :type item_type: ItemType
        :returns: the VAT rate in percent.
        :rtype: decimal.Decimal
        """

        raise NotImplementedError()

    def get_sale_to_country_vat_charge(self,
                                       date,
                                       item_type,
                                       buyer,
                                       seller):
        """Get the VAT charge for selling an item to a buyer in the country.

        :param date: Sale date.
        :type date: datetime.date
        :param item_type: Type of the item being sold.
        :type item_type: ItemType
        :param buyer: Buyer.
        :type buyer: Party
        :param seller: Seller.
        :type seller: Party
        :rtype: VatCharge
        :raises NotImplementedError:
            if no explicit rules for selling to the given country from the
            given country exist. VAT charge determining falls back to testing
            rules for the country in which the seller resides if this is
            raised.
        """

        raise NotImplementedError()

    def get_sale_from_country_vat_charge(self,
                                         date,
                                         item_type,
                                         buyer,
                                         seller):
        """Get the VAT charge for selling an item as a seller in the country.

        :param date: Sale date.
        :type date: datetime.date
        :param item_type: Type of the item being sold.
        :type item_type: ItemType
        :param buyer: Buyer.
        :type buyer: Party
        :param seller: Seller.
        :type seller: Party
        :rtype: VatCharge
        :raises NotImplementedError:
            if no rules for selling from the given country to the given country
            exist.
        """

        raise NotImplementedError()


class EuVatRulesMixin(object):
    """Mixin for VAT rules in EU countries.
    """

    def get_sale_to_country_vat_charge(self,
                                       date,
                                       item_type,
                                       buyer,
                                       seller):
        # We only support business sellers at this time.
        if not seller.is_business:
            raise NotImplementedError(
                'non-business sellers are currently not supported'
            )

        # If the seller resides in the same country as the buyer, we charge
        # VAT regardless of whether the buyer is a business or not. Similarly,
        # if the buyer is a consumer, we must charge VAT in the buyer's country
        # of residence.
        if seller.country_code == buyer.country_code or \
                (not buyer.is_business and date >= JANUARY_1_2015):
            return VatCharge(VatChargeAction.charge,
                             buyer.country_code,
                             self.get_vat_rate(item_type))

        # EU consumers are charged VAT in the seller's country prior to January
        # 1st, 2015.
        if not buyer.is_business:
            # Fall back to the seller's VAT rules for this one.
            raise NotImplementedError()

        # EU businesses will never be charged VAT but must account for the VAT
        # by the reverse-charge mechanism.
        return VatCharge(VatChargeAction.reverse_charge,
                         buyer.country_code,
                         0)

    def get_sale_from_country_vat_charge(self,
                                         date,
                                         item_type,
                                         buyer,
                                         seller):
        # We only support business sellers at this time.
        if not seller.is_business:
            raise NotImplementedError(
                'non-business sellers are currently not supported'
            )

        # If the buyer resides outside the EU, we do not have to charge VAT.
        if buyer.country_code not in EU_COUNTRY_CODES:
            return VatCharge(VatChargeAction.no_charge, buyer.country_code, 0)

        # Both businesses and consumers are charged VAT in the seller's
        # country if both seller and buyer reside in the same country.
        if buyer.country_code == seller.country_code:
            return VatCharge(VatChargeAction.charge,
                             seller.country_code,
                             self.get_vat_rate(item_type))

        # Businesses in other EU countries are not charged VAT but are
        # responsible for accounting for the tax through the reverse-charge
        # mechanism.
        if buyer.is_business:
            return VatCharge(VatChargeAction.reverse_charge,
                             buyer.country_code,
                             0)

        # Consumers in other EU countries are charged VAT in their country of
        # residence after January 1st, 2015. Before this date, you charge VAT
        # in the country where the company is located.
        if date >= datetime.date(2015, 1, 1):
            buyer_rules = VAT_RULES[buyer.country_code]

            return VatCharge(VatChargeAction.charge,
                             buyer.country_code,
                             buyer_rules.get_vat_rate(item_type))
        else:
            return VatCharge(VatChargeAction.charge,
                             seller.country_code,
                             self.get_vat_rate(item_type))


class ConstantEuVatRateRules(EuVatRulesMixin):
    """VAT rules for a country with a constant VAT rate in the entiry country.
    """

    def __init__(self, vat_rate):
        self.vat_rate = ensure_decimal(vat_rate)

    def get_vat_rate(self, item_type):
        return self.vat_rate


class AtVatRules(EuVatRulesMixin):
    """VAT rules for Austria.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.prepaid_broadcasting_service:
            return Decimal(10)
        elif item_type == ItemType.ebook:
            return Decimal(10)
        return Decimal(20)


class CzVatRules(ConstantEuVatRateRules):
    """VAT rules for Czech Republic.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(10)

        return super(CzVatRules, self).get_vat_rate(item_type)


class BeVatRules(ConstantEuVatRateRules):
    """VAT rules for Belgium.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(6)

        return super(BeVatRules, self).get_vat_rate(item_type)


class IeVatRules(ConstantEuVatRateRules):
    """VAT rules for Ireland.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(9)

        return super(IeVatRules, self).get_vat_rate(item_type)


class FiVatRules(ConstantEuVatRateRules):
    """VAT rules for  Finland.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(10)

        return super(FiVatRules, self).get_vat_rate(item_type)


class NlVatRules(ConstantEuVatRateRules):
    """VAT rules for Netherlands.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(9)

        return super(NlVatRules, self).get_vat_rate(item_type)


class MtVatRules(ConstantEuVatRateRules):
    """VAT rules for Malta.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(5)

        return super(MtVatRules, self).get_vat_rate(item_type)


class SeVatRules(ConstantEuVatRateRules):
    """VAT rules for Sweden.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(6)

        return super(SeVatRules, self).get_vat_rate(item_type)


class HrVatRules(ConstantEuVatRateRules):
    """VAT rules for Croatia.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(5)

        return super(HrVatRules, self).get_vat_rate(item_type)


class PtVatRules(ConstantEuVatRateRules):
    """VAT rules for Portugal.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(6)

        return super(PtVatRules, self).get_vat_rate(item_type)


class FrVatRules(EuVatRulesMixin):
    """VAT rules for France.
    """

    def get_vat_rate(self, item_type):
        if item_type.is_broadcasting_service:
            return Decimal(10)
        if item_type == ItemType.ebook:
            return Decimal('5.5')
        if item_type == ItemType.enewspaper:
            return Decimal('2.1')
        return Decimal(20)


class ElVatRules(EuVatRulesMixin):
    """VAT rules for Greece.
    """

    def get_vat_rate(self, item_type):
        return Decimal(24)


class LuVatRules(EuVatRulesMixin):
    """VAT rules for Luxembourg.
    """

    def get_vat_rate(self, item_type):
        if item_type.is_broadcasting_service:
            return Decimal(3)
        elif item_type == ItemType.ebook:
            return Decimal(3)
        return Decimal(17)


class PlVatRules(EuVatRulesMixin):
    """VAT rules for Poland.
    """

    def get_vat_rate(self, item_type):
        if item_type.is_broadcasting_service:
            return Decimal(8)
        if item_type == ItemType.ebook:
            return Decimal(5)
        return Decimal(23)


class EsVatRules(EuVatRulesMixin):
    """VAT rules for Spain.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(4)
        return Decimal(21)


class DeVatRules(EuVatRulesMixin):
    """VAT rules for Germany.
    """

    def get_vat_rate(self, item_type):
        if item_type == ItemType.ebook:
            return Decimal(7)
        return Decimal(19)


# VAT rates are based on the report from January 1st, 2020
# http://ec.europa.eu/taxation_customs/sites/taxation/files/resources/documents/taxation/vat/how_vat_works/rates/vat_rates_en.pdf
VAT_RULES = {
    'AT': AtVatRules(),
    'BE': BeVatRules(21),
    'BG': ConstantEuVatRateRules(20),
    'CY': ConstantEuVatRateRules(19),
    'CZ': CzVatRules(21),
    'DE': DeVatRules(),
    'DK': ConstantEuVatRateRules(25),
    'EE': ConstantEuVatRateRules(22),
    'EL': ElVatRules(),
    'GR': ElVatRules(),  # Synonymous country code for Greece
    'ES': EsVatRules(),
    'FI': FiVatRules(24),
    'FR': FrVatRules(),
    'HR': HrVatRules(25),
    'HU': ConstantEuVatRateRules(27),
    'IE': IeVatRules(23),
    'IT': ConstantEuVatRateRules(22),
    'LT': ConstantEuVatRateRules(21),
    'LU': LuVatRules(),
    'LV': ConstantEuVatRateRules(21),
    'MT': MtVatRules(18),
    'NL': NlVatRules(21),
    'PL': PlVatRules(),
    'PT': PtVatRules(23),
    'RO': ConstantEuVatRateRules(19),
    'SE': SeVatRules(25),
    'SK': ConstantEuVatRateRules(20),
    'SI': ConstantEuVatRateRules(22),
}

"""VAT rules by country.

Maps an ISO 3316 alpha-2 country code to the VAT rules applicable in the given
country.
"""
