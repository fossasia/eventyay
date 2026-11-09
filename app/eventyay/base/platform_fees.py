from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from eventyay.base.signals import platform_fee_policy


if TYPE_CHECKING:
    from eventyay.base.models import Event, Order, OrderPayment


@dataclass(frozen=True, slots=True)
class PlatformFeePolicy:
    percentage: Decimal = Decimal('0.00')
    maximum_fee: Decimal = Decimal('0.00')
    is_override: bool = False
    source: str = ''

    def __post_init__(self) -> None:
        if not isinstance(self.percentage, Decimal):
            raise TypeError('Platform fee percentage must be a Decimal.')
        if not isinstance(self.maximum_fee, Decimal):
            raise TypeError('Platform fee maximum must be a Decimal.')
        if not self.percentage.is_finite():
            raise ValueError('Platform fee percentage must be finite.')
        if not self.maximum_fee.is_finite():
            raise ValueError('Platform fee maximum must be finite.')
        if self.percentage < 0 or self.percentage > 100:
            raise ValueError('Platform fee percentage must be between 0 and 100.')
        if self.maximum_fee < 0:
            raise ValueError('Platform fee maximum cannot be negative.')


class MultiplePlatformFeePoliciesError(RuntimeError):
    pass


def resolve_platform_fee_policy(*, event: Event, order: Order, payment: OrderPayment) -> PlatformFeePolicy:
    responses = platform_fee_policy.send(
        sender=event,
        order=order,
        payment=payment,
    )
    policies = []
    for receiver, response in responses:
        if response is None:
            continue
        if not isinstance(response, PlatformFeePolicy):
            raise TypeError(
                f'Platform fee provider {receiver!r} returned '
                f'{type(response).__name__}, expected PlatformFeePolicy or None.'
            )
        policies.append(response)

    if len(policies) > 1:
        raise MultiplePlatformFeePoliciesError('Multiple plugins provided a platform fee policy for the same payment.')
    if policies:
        return policies[0]
    return PlatformFeePolicy()
