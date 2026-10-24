import datetime
import os
import socket
from unittest.mock import MagicMock, patch

import pytest
from django.db.models import Case, TextField
from django.db.models.functions import Concat
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User, Voucher
from eventyay.base.services.vouchers import vouchers_send


def test_vouchers_send_preserves_existing_comment():
    """Verify vouchers_send appends sent-to note to existing voucher comments without overwriting (#6645)."""
    mock_event = MagicMock()
    mock_event.settings.locale = 'en'

    mock_voucher = MagicMock()
    mock_voucher.id = 1
    mock_voucher.code = 'VOUCHER1'
    mock_voucher.tag = None
    mock_voucher.comment = 'Reserved for keynote speaker'

    mock_user = MagicMock()

    with (
        patch('eventyay.base.services.vouchers.Voucher.objects.filter') as mock_v_filter,
        patch('eventyay.base.services.vouchers.User.objects.get', return_value=mock_user),
        patch('eventyay.base.services.vouchers.LogEntry.objects.bulk_create'),
        patch('eventyay.base.services.vouchers.get_email_context', return_value={}),
        patch('eventyay.base.services.vouchers.mail'),
    ):
        mock_qs = MagicMock()
        mock_qs.order_by.return_value = [mock_voucher]
        mock_v_filter.return_value = mock_qs

        vouchers_send(
            event=mock_event,
            vouchers=[1],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'email': 'speaker@example.com', 'number': 1}],
            user=42,
        )

        assert mock_voucher.comment == (
            'Reserved for keynote speaker\n\n'
            'The voucher has been sent to speaker@example.com.'
        )
        mock_qs.update.assert_called_once()
        call_kwargs = mock_qs.update.call_args.kwargs
        assert isinstance(call_kwargs['comment'], Case)


def test_vouchers_send_sets_note_when_no_prior_comment():
    """Verify vouchers_send sets sent-to note without leading newlines when no comment exists (#6645)."""
    mock_event = MagicMock()
    mock_event.settings.locale = 'en'

    mock_voucher = MagicMock()
    mock_voucher.id = 2
    mock_voucher.code = 'VOUCHER2'
    mock_voucher.tag = None
    mock_voucher.comment = None

    mock_user = MagicMock()

    with (
        patch('eventyay.base.services.vouchers.Voucher.objects.filter') as mock_v_filter,
        patch('eventyay.base.services.vouchers.User.objects.get', return_value=mock_user),
        patch('eventyay.base.services.vouchers.LogEntry.objects.bulk_create'),
        patch('eventyay.base.services.vouchers.get_email_context', return_value={}),
        patch('eventyay.base.services.vouchers.mail'),
    ):
        mock_qs = MagicMock()
        mock_qs.order_by.return_value = [mock_voucher]
        mock_v_filter.return_value = mock_qs

        vouchers_send(
            event=mock_event,
            vouchers=[2],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'email': 'attendee@example.com', 'number': 1}],
            user=42,
        )

        assert mock_voucher.comment == 'The voucher has been sent to attendee@example.com.'
        mock_qs.update.assert_called_once()
        call_kwargs = mock_qs.update.call_args.kwargs
        assert isinstance(call_kwargs['comment'], Case)


def test_vouchers_send_multiple_recipients():
    """Verify vouchers_send handles multiple recipients and updates each voucher's comment correctly (#6645)."""
    mock_event = MagicMock()
    mock_event.settings.locale = 'en'

    v1 = MagicMock(id=1, code='CODE1', tag=None, comment='Existing note')
    v2 = MagicMock(id=2, code='CODE2', tag=None, comment='')

    mock_user = MagicMock()

    with (
        patch('eventyay.base.services.vouchers.Voucher.objects.filter') as mock_v_filter,
        patch('eventyay.base.services.vouchers.User.objects.get', return_value=mock_user),
        patch('eventyay.base.services.vouchers.LogEntry.objects.bulk_create'),
        patch('eventyay.base.services.vouchers.get_email_context', return_value={}),
        patch('eventyay.base.services.vouchers.mail'),
    ):
        mock_qs = MagicMock()
        mock_qs.order_by.return_value = [v1, v2]
        mock_v_filter.return_value = mock_qs

        vouchers_send(
            event=mock_event,
            vouchers=[1, 2],
            subject='Your vouchers',
            message='Here are your vouchers: {voucher_list}',
            recipients=[
                {'email': 'user1@example.com', 'number': 1},
                {'email': 'user2@example.com', 'number': 1},
            ],
            user=1,
        )

        # vouchers.pop() pops from the end, so v2 is user1 and v1 is user2
        assert 'The voucher has been sent to user1@example.com.' in v2.comment
        assert not v2.comment.startswith('\n')
        assert v1.comment == 'Existing note\n\nThe voucher has been sent to user2@example.com.'
        assert mock_qs.update.call_count == 2


def test_vouchers_send_atomic_update_expression_prevents_stale_comment_overwrite():
    """Verify vouchers_send uses atomic Case/Concat expression on database column (#6645).

    Rather than writing the stale in-memory comment with bulk_update, it updates the
    database row atomically using Concat('comment', ...), ensuring concurrent organizer
    edits to the voucher comment are not overwritten.
    """
    mock_event = MagicMock()
    mock_event.settings.locale = 'en'

    mock_voucher = MagicMock(id=10, code='V10', tag='old_tag', comment='Original')
    mock_user = MagicMock()

    with (
        patch('eventyay.base.services.vouchers.Voucher.objects.filter') as mock_v_filter,
        patch('eventyay.base.services.vouchers.User.objects.get', return_value=mock_user),
        patch('eventyay.base.services.vouchers.LogEntry.objects.bulk_create'),
        patch('eventyay.base.services.vouchers.get_email_context', return_value={}),
        patch('eventyay.base.services.vouchers.mail'),
    ):
        mock_qs = MagicMock()
        mock_qs.order_by.return_value = [mock_voucher]
        mock_v_filter.return_value = mock_qs

        vouchers_send(
            event=mock_event,
            vouchers=[10],
            subject='Subject',
            message='Message: {voucher_list}',
            recipients=[{'email': 'test@example.com', 'number': 1, 'tag': 'new_tag'}],
            user=1,
        )

        # Ensure filter called for voucher IDs update
        mock_v_filter.assert_called_with(id__in=[10])
        mock_qs.update.assert_called_once()

        call_kwargs = mock_qs.update.call_args.kwargs
        assert call_kwargs['tag'] == 'new_tag'

        case_expr = call_kwargs['comment']
        assert isinstance(case_expr, Case)
        assert isinstance(case_expr.output_field, TextField)
        # Default expression must be Concat referencing the DB 'comment' field
        assert isinstance(case_expr.default, Concat)
        assert isinstance(case_expr.default.output_field, TextField)
        default_repr = repr(case_expr.default)
        assert 'comment' in default_repr
        assert 'The voucher has been sent to test@example.com.' in default_repr


def _is_db_available():
    if os.environ.get('CI') == 'true':
        return True
    if os.path.exists('/var/run/postgresql/.s.PGSQL.5432'):
        return True
    try:
        with socket.create_connection(('127.0.0.1', 5432), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _is_db_available(), reason='PostgreSQL database is not available')
@pytest.mark.django_db
def test_vouchers_send_database_backed_event_scoped_update():
    """Verify vouchers_send persists comment updates to the real DB with event scoping (#6645).

    Exercises the real event-scoped update instead of mocking Voucher.objects.filter.
    Covers vouchers with existing and empty comments, refreshes them from the database,
    asserts persisted comment values, and verifies that a voucher from another event
    remains unchanged.
    """
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Organizer A', slug='org-a-vs')
        event1 = Event.objects.create(
            organizer=organizer,
            name='Event 1',
            slug='event-1-vs',
            date_from=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        event2 = Event.objects.create(
            organizer=organizer,
            name='Event 2',
            slug='event-2-vs',
            date_from=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        user = User.objects.create_user('admin-vs@example.com', 'dummy')

        v1 = Voucher.objects.create(
            event=event1,
            code='VOUCHER1',
            comment='Existing staff comment',
        )
        v2 = Voucher.objects.create(
            event=event1,
            code='VOUCHER2',
            comment='',
        )
        v_other = Voucher.objects.create(
            event=event2,
            code='VOUCHER_OTHER',
            comment='Other event comment',
        )

    with (
        patch('eventyay.base.services.vouchers.mail'),
        patch('eventyay.base.services.vouchers.get_email_context', return_value={}),
    ):
        vouchers_send(
            event=event1,
            vouchers=[v1.id, v2.id, v_other.id],
            subject='Your voucher',
            message='Code: {voucher_list}',
            recipients=[
                {'email': 'recipient1@example.com', 'number': 1},
                {'email': 'recipient2@example.com', 'number': 1},
            ],
            user=user.id,
        )

    v1.refresh_from_db()
    v2.refresh_from_db()
    v_other.refresh_from_db()

    # vouchers.pop() assigns v2 to recipient1 and v1 to recipient2
    assert v1.comment == (
        'Existing staff comment\n\n'
        'The voucher has been sent to recipient2@example.com.'
    )
    assert v2.comment == 'The voucher has been sent to recipient1@example.com.'
    assert v_other.comment == 'Other event comment'
