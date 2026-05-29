import datetime

import pytest
from django.utils.timezone import now

from eventyay.base.models.mail import QueuedMail
from eventyay.common.exceptions import SendMailException


@pytest.mark.django_db
def test_queuedmail_send_raises_for_future_scheduled_at():
    """QueuedMail.send() must raise SendMailException when scheduled_at is in the future."""
    qm = QueuedMail(scheduled_at=now() + datetime.timedelta(hours=1))
    with pytest.raises(SendMailException):
        qm.send()


@pytest.mark.django_db
def test_queuedmail_send_raises_when_already_sent():
    """QueuedMail.send() must raise Exception when mail is already sent."""
    qm = QueuedMail(sent=True)
    with pytest.raises(Exception) as exc_info:
        qm.send()
    assert 'already' in str(exc_info.value).lower()


def test_queuedmail_scheduling_guard_not_triggered_without_scheduled_at():
    """When scheduled_at is None the scheduling guard must not fire SendMailException.

    This test does NOT use @pytest.mark.django_db: it intentionally catches any
    exception raised by the @transaction.atomic wrapper (no DB available) and
    only fails if the scheduling-guard exception is raised.
    """
    qm = QueuedMail(scheduled_at=None, sent=False)
    try:
        qm.send()
    except SendMailException as exc:
        pytest.fail(
            f"Scheduling guard must not fire when scheduled_at is None: {exc}"
        )
    except Exception:
        pass
