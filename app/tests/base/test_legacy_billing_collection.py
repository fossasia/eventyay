from unittest.mock import MagicMock, patch

import pytest
from django.dispatch import Signal

from eventyay.base import signals as base_signals
from eventyay.base.signals import is_legacy_billing_collection_disabled
from eventyay.eventyay_common import tasks


@pytest.fixture
def legacy_billing_signal(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(base_signals, "legacy_billing_collection_disabled", signal)
    return signal


def test_legacy_billing_stays_enabled_without_provider(legacy_billing_signal):
    assert is_legacy_billing_collection_disabled(MagicMock()) is False


def test_legacy_billing_can_be_disabled_by_provider(legacy_billing_signal):
    organizer = MagicMock()

    def provider(sender, **kwargs):
        assert sender is organizer
        assert kwargs["organizer"] is organizer
        return True

    legacy_billing_signal.connect(provider)

    assert is_legacy_billing_collection_disabled(organizer) is True


def test_legacy_billing_fails_closed_when_provider_errors(
    legacy_billing_signal, caplog
):
    def provider(sender, **kwargs):
        raise RuntimeError("provider unavailable")

    legacy_billing_signal.connect(provider)

    assert is_legacy_billing_collection_disabled(MagicMock()) is True
    assert "Legacy billing ownership provider" in caplog.text
    assert isinstance(caplog.records[0].exc_info[1], RuntimeError)


def test_monthly_billing_skips_externally_managed_organizer():
    organizer = MagicMock(slug="managed-organizer")
    with patch(
        "eventyay.eventyay_common.tasks.Organizer.objects.all",
        return_value=[organizer],
    ), patch(
        "eventyay.eventyay_common.tasks.is_legacy_billing_collection_disabled",
        return_value=True,
    ) as disabled, patch(
        "eventyay.eventyay_common.tasks.collect_billing_invoice"
    ) as collect:
        tasks.monthly_billing_collect.run()

    disabled.assert_called_once_with(organizer)
    collect.assert_not_called()


def test_legacy_auto_charge_skips_externally_managed_organizer():
    organizer = MagicMock(slug="managed-organizer")
    invoice = MagicMock(organizer=organizer, final_ticket_fee=10)
    with patch(
        "eventyay.eventyay_common.tasks.BillingInvoice.objects.filter",
        return_value=[invoice],
    ), patch(
        "eventyay.eventyay_common.tasks.is_legacy_billing_collection_disabled",
        return_value=True,
    ) as disabled, patch(
        "eventyay.eventyay_common.tasks.process_auto_billing_charge_stripe"
    ) as charge:
        tasks.process_auto_billing_charge.run()

    disabled.assert_called_once_with(organizer)
    charge.assert_not_called()
