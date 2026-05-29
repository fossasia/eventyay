import datetime

import pytest
from django import forms
from django.utils.timezone import now

from eventyay.common.exceptions import SendMailException
from eventyay.common.forms.mixins import ScheduledAtValidationMixin
from eventyay.plugins.sendmail.models import EmailQueue


def test_emailqueue_send_raises_when_scheduled_in_future():
    """Scheduling guard: send() must raise SendMailException for future-dated emails."""
    qm = EmailQueue(scheduled_at=now() + datetime.timedelta(hours=1))
    with pytest.raises(SendMailException):
        qm.send()


def test_emailqueue_send_no_scheduling_guard_without_scheduled_at():
    """When scheduled_at is None the scheduling guard must not raise SendMailException."""
    qm = EmailQueue(scheduled_at=None)
    try:
        qm.send()
    except SendMailException as exc:
        pytest.fail(
            f"Scheduling guard must not fire when scheduled_at is None: {exc}"
        )
    except Exception:
        pass


class _SimpleScheduledForm(ScheduledAtValidationMixin, forms.Form):
    """Minimal form to exercise the shared mixin in isolation."""
    scheduled_at = forms.SplitDateTimeField(required=False)


def test_scheduled_at_mixin_rejects_past_timestamp():
    """ScheduledAtValidationMixin must reject a timestamp in the past."""
    past_dt = now() - datetime.timedelta(hours=2)
    form = _SimpleScheduledForm(data={
        'scheduled_at_0': past_dt.strftime('%Y-%m-%d'),
        'scheduled_at_1': past_dt.strftime('%H:%M:%S'),
    })
    assert not form.is_valid()
    assert 'scheduled_at' in form.errors


def test_scheduled_at_mixin_accepts_future_timestamp():
    """ScheduledAtValidationMixin must accept a timestamp comfortably in the future."""
    future_dt = now() + datetime.timedelta(hours=2)
    form = _SimpleScheduledForm(data={
        'scheduled_at_0': future_dt.strftime('%Y-%m-%d'),
        'scheduled_at_1': future_dt.strftime('%H:%M:%S'),
    })
    assert form.is_valid(), form.errors


def test_scheduled_at_mixin_accepts_empty():
    """ScheduledAtValidationMixin must accept an empty (immediate send) value."""
    form = _SimpleScheduledForm(data={'scheduled_at_0': '', 'scheduled_at_1': ''})
    assert form.is_valid(), form.errors
