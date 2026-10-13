from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.dispatch import Signal

from eventyay.base import platform_fees
from eventyay.base.platform_fees import (
    MultiplePlatformFeePoliciesError,
    PlatformFeePolicy,
    resolve_platform_fee_policy,
)


@pytest.fixture
def fee_signal(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(platform_fees, 'platform_fee_policy', signal)
    return signal


def test_platform_fee_defaults_to_zero_without_provider(fee_signal):
    policy = resolve_platform_fee_policy(event=MagicMock(), order=MagicMock(), payment=MagicMock())

    assert policy == PlatformFeePolicy()
    assert policy.percentage == Decimal('0.00')


def test_platform_fee_returns_provider_policy(fee_signal):
    event = MagicMock()
    order = MagicMock()
    payment = MagicMock()
    expected = PlatformFeePolicy(
        percentage=Decimal('5.00'),
        maximum_fee=Decimal('20.00'),
        is_override=True,
        source='business',
    )

    def provider(sender, order, payment, **kwargs):
        assert sender is event
        assert order is not None
        assert payment is not None
        return expected

    fee_signal.connect(provider)

    assert resolve_platform_fee_policy(event=event, order=order, payment=payment) == expected


def test_platform_fee_ignores_provider_without_policy(fee_signal):
    fee_signal.connect(lambda sender, **kwargs: None, weak=False)

    policy = resolve_platform_fee_policy(event=MagicMock(), order=MagicMock(), payment=MagicMock())

    assert policy == PlatformFeePolicy()


def test_platform_fee_rejects_invalid_provider_response(fee_signal):
    fee_signal.connect(
        lambda sender, **kwargs: Decimal('5.00'),
        weak=False,
    )

    with pytest.raises(TypeError, match='expected PlatformFeePolicy or None'):
        resolve_platform_fee_policy(event=MagicMock(), order=MagicMock(), payment=MagicMock())


def test_platform_fee_rejects_multiple_policies(fee_signal):
    fee_signal.connect(
        lambda sender, **kwargs: PlatformFeePolicy(percentage=Decimal('5.00')),
        weak=False,
    )
    fee_signal.connect(
        lambda sender, **kwargs: PlatformFeePolicy(percentage=Decimal('2.00')),
        weak=False,
    )

    with pytest.raises(MultiplePlatformFeePoliciesError):
        resolve_platform_fee_policy(event=MagicMock(), order=MagicMock(), payment=MagicMock())


@pytest.mark.parametrize(
    ('field', 'value', 'error'),
    [
        ('percentage', Decimal('-0.01'), 'between 0 and 100'),
        ('percentage', Decimal('100.01'), 'between 0 and 100'),
        ('percentage', Decimal('Infinity'), 'must be finite'),
        ('percentage', Decimal('NaN'), 'must be finite'),
        ('maximum_fee', Decimal('-0.01'), 'cannot be negative'),
        ('maximum_fee', Decimal('Infinity'), 'must be finite'),
        ('maximum_fee', Decimal('NaN'), 'must be finite'),
    ],
)
def test_platform_fee_policy_rejects_invalid_values(field, value, error):
    with pytest.raises(ValueError, match=error):
        PlatformFeePolicy(**{field: value})
