from unittest.mock import MagicMock

import pytest
from django.dispatch import Signal

from eventyay.base import entitlements
from eventyay.base.entitlements import (
    EntitlementDecision,
    check_entitlement,
    get_capability_registry,
    record_usage,
)
from eventyay.base.signals import entitlement_check


@pytest.fixture
def dummy_organizer():
    return MagicMock()


@pytest.mark.django_db
def test_check_entitlement_default_allow(dummy_organizer):
    """If no receivers block it, it should return an allowed decision."""
    decision = check_entitlement(dummy_organizer, capability="some_capability")
    assert decision.allowed is True


@pytest.mark.django_db
def test_check_entitlement_denied_bool(dummy_organizer):
    """If a receiver returns False, it should return a denied decision (legacy fallback)."""
    
    def deny_receiver(sender, capability, **kwargs):
        if capability == "restricted_feature":
            return False
        return True

    entitlement_check.connect(deny_receiver)
    try:
        decision_denied = check_entitlement(dummy_organizer, capability="restricted_feature")
        assert decision_denied.allowed is False
        assert decision_denied.reason_code == "denied_by_plugin"
        
        decision_allowed = check_entitlement(dummy_organizer, capability="other_feature")
        assert decision_allowed.allowed is True
    finally:
        entitlement_check.disconnect(deny_receiver)


@pytest.mark.django_db
def test_check_entitlement_denied_decision(dummy_organizer):
    """If a receiver returns a denied EntitlementDecision, it should return that decision."""
    
    def deny_receiver(sender, capability, **kwargs):
        if capability == "restricted_feature":
            return EntitlementDecision(allowed=False, reason_code="limit_reached", limit=10, used=10)
        return EntitlementDecision(allowed=True, limit=10, used=5)

    entitlement_check.connect(deny_receiver)
    try:
        decision_denied = check_entitlement(dummy_organizer, capability="restricted_feature")
        assert decision_denied.allowed is False
        assert decision_denied.reason_code == "limit_reached"
        assert decision_denied.limit == 10
        assert decision_denied.used == 10
        
        decision_allowed = check_entitlement(dummy_organizer, capability="other_feature")
        assert decision_allowed.allowed is True
        assert decision_allowed.limit == 10
        assert decision_allowed.used == 5
    finally:
        entitlement_check.disconnect(deny_receiver)


@pytest.fixture
def usage_signal(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(entitlements, 'entitlement_usage_recorded', signal)
    return signal


@pytest.fixture
def registry_signal(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(entitlements, 'register_entitlements', signal)
    return signal


@pytest.mark.django_db
def test_record_usage(dummy_organizer, usage_signal):
    """Test that record_usage dispatches the correct signal."""
    received = []

    def usage_receiver(sender, **kwargs):
        received.append((sender, kwargs))

    usage_signal.connect(usage_receiver)
    record_usage(
        dummy_organizer,
        'test_cap',
        quantity=5,
        unit='emails',
        source_type='bulk_email',
        source_id='42',
        idempotency_key='bulk_mail_42',
    )
    assert len(received) == 1
    sender, kwargs = received[0]
    assert sender is dummy_organizer
    assert kwargs['capability'] == 'test_cap'
    assert kwargs['quantity'] == 5
    assert kwargs['unit'] == 'emails'
    assert kwargs['source_type'] == 'bulk_email'
    assert kwargs['source_id'] == '42'
    assert kwargs['idempotency_key'] == 'bulk_mail_42'
    assert kwargs['event'] is None
    assert kwargs['metadata'] is None


@pytest.mark.django_db
def test_record_usage_matches_strict_receiver(dummy_organizer, usage_signal):
    """
    Receivers such as the eventyay-business plugin take the usage fields as
    required arguments, so record_usage has to send every one of them.
    """
    received = []

    def strict_receiver(
        sender, capability, quantity, unit, source_type, source_id, idempotency_key, event=None, metadata=None, **kwargs
    ):
        received.append((capability, quantity, idempotency_key))

    usage_signal.connect(strict_receiver)
    record_usage(
        dummy_organizer,
        'registration.free_allowance_per_event',
        quantity=2,
        unit='registrations',
        source_type='order',
        source_id='ABC12',
        idempotency_key='order_ABC12_free_registrations',
    )
    assert received == [('registration.free_allowance_per_event', 2, 'order_ABC12_free_registrations')]


@pytest.mark.django_db
def test_record_usage_requires_quantity_by_keyword(dummy_organizer, usage_signal):
    fields = dict(unit='emails', source_type='bulk_email', source_id='42', idempotency_key='bulk_mail_42')
    with pytest.raises(TypeError):
        record_usage(dummy_organizer, 'test_cap', **fields)
    with pytest.raises(TypeError):
        record_usage(dummy_organizer, 'test_cap', 5, **fields)


USAGE_FIELDS = {
    'quantity': 2,
    'unit': 'registrations',
    'source_type': 'order',
    'source_id': 'ABC12',
    'idempotency_key': 'order_ABC12_free_registrations',
}


@pytest.mark.django_db
@pytest.mark.parametrize('missing', list(USAGE_FIELDS))
def test_record_usage_requires_each_usage_field(dummy_organizer, usage_signal, missing):
    """
    Each usage field is required: leaving one out must fail in record_usage
    itself, before any receiver sees a partial usage record.
    """
    received = []

    def usage_receiver(sender, **kwargs):
        received.append(kwargs)

    usage_signal.connect(usage_receiver)
    fields = {name: value for name, value in USAGE_FIELDS.items() if name != missing}
    with pytest.raises(TypeError, match=missing):
        record_usage(dummy_organizer, 'registration.free_allowance_per_event', **fields)
    assert received == []


@pytest.mark.django_db
def test_get_capability_registry(registry_signal):
    """Test that get_capability_registry merges dictionaries correctly."""
    
    def reg_receiver_1(sender, **kwargs):
        return {"cap1": "Description 1"}

    def reg_receiver_2(sender, **kwargs):
        return {"cap2": "Description 2"}

    def reg_receiver_invalid(sender, **kwargs):
        return ["invalid list"]

    registry_signal.connect(reg_receiver_1)
    registry_signal.connect(reg_receiver_2)
    registry_signal.connect(reg_receiver_invalid)
    
    registry = get_capability_registry()
    assert registry == {
        "cap1": "Description 1",
        "cap2": "Description 2",
    }

@pytest.mark.django_db
def test_check_entitlement_empty_capability(dummy_organizer):
    """Empty capabilities should raise ValueError to prevent fail-open security bypass."""
    with pytest.raises(ValueError, match="Capability cannot be empty"):
        check_entitlement(dummy_organizer, capability="")
