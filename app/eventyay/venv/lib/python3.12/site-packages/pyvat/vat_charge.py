from enum import Enum
from .utils import ensure_decimal


class VatChargeAction(Enum):
    """VAT charge action.
    """

    charge = 1
    """Charge VAT.
    """

    reverse_charge = 2
    """No VAT charged but customer is required to account via reverse-charge.
    """

    no_charge = 3
    """No VAT charged.
    """


class VatCharge(object):
    """VAT charge.

    :ivar action: VAT charge action.
    :type action: VatChargeAction
    :ivar country_code:
        Country in which the action applies as the ISO 3166-1 alpha-2 code of
        the country.
    :type country_code: str
    :ivar rate:
        VAT rate in percent. I.e. a value of 25 indicates a VAT charge of 25 %.
    :type rate: Decimal
    """

    def __init__(self, action, country_code, rate):
        self.action = action
        self.country_code = country_code
        self.rate = ensure_decimal(rate)

    def __repr__(self):
        return '<%s.%s: action = %r, country code = %r, rate = %s>' % (
            self.__class__.__module__,
            self.__class__.__name__,
            self.action,
            self.country_code,
            self.rate,
        )
