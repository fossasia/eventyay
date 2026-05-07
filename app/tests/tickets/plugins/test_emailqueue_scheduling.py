import datetime

import pytest
from django.utils.timezone import now

from eventyay.common.exceptions import SendMailException
from eventyay.plugins.sendmail.models import EmailQueue


def test_emailqueue_send_raises_when_scheduled_in_future():
    """Scheduling guard: send() must raise SendMailException for future-dated emails."""
    qm = EmailQueue(scheduled_at=now() + datetime.timedelta(hours=1))
    with pytest.raises(SendMailException):
        qm.send()
