"""Tests for Event.clear_data(), the routine that scrubs personal data from an event.

`clear_data()` opened with `self.audit_logs.all().delete()`, but `audit_logs` is the
related_name on `AuditLog.user`, not on `AuditLog.event` - the event side is `audits`.
Every call therefore raised `AttributeError` on the first statement and nothing was ever
scrubbed. `delete_sub_objects()` in the same model already used the correct `self.audits`.

The relation tests below need no database and would have caught that on their own.
"""

import os

import pytest
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Organizer
from eventyay.base.models.storage_model import StoredFile


# Reverse relations Event.clear_data() dereferences directly off `self`.
CLEAR_DATA_RELATIONS = [
    'audits',
    'event_grants',
    'room_grants',
    'bbb_calls',
    'user_set',
]


@pytest.mark.parametrize('relation', CLEAR_DATA_RELATIONS)
def test_event_has_relations_used_by_clear_data(relation):
    assert hasattr(Event, relation), f'Event.clear_data() dereferences self.{relation}, which does not exist on Event'


def test_event_has_no_audit_logs_relation():
    """`audit_logs` belongs to User, not Event. Using it in clear_data() was the bug."""
    assert not hasattr(Event, 'audit_logs')


@pytest.fixture
def scrub_event():
    organizer = Organizer.objects.create(name='Dummy Scrub', slug='dummy-scrub')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy Scrub Event',
        slug='dummy-scrub-event',
        date_from=now(),
    )
    with scope(organizer=organizer):
        yield event


@pytest.mark.django_db
def test_clear_data_runs_on_an_empty_event(scrub_event):
    """Regression: this raised AttributeError before reaching any deletion."""
    scrub_event.clear_data()

    scrub_event.refresh_from_db()
    assert scrub_event.domain is None


@pytest.mark.django_db
def test_clear_data_removes_stored_files_after_commit(scrub_event, django_capture_on_commit_callbacks):
    """Rows go inside the transaction; the file itself is removed only once it commits."""
    stored_file = StoredFile.objects.create(
        event=scrub_event,
        date=now(),
        filename='Screenshot.png',
        type='image/png',
        file=ContentFile('', 'Screenshot.png'),
        public=True,
    )
    path = stored_file.file.path
    assert os.path.exists(path)

    with django_capture_on_commit_callbacks(execute=True):
        scrub_event.clear_data()

    assert not StoredFile.objects.filter(event=scrub_event).exists()
    assert not os.path.exists(path)
