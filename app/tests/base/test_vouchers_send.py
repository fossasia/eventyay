import datetime

import pytest
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer, User
from eventyay.base.services.vouchers import vouchers_send


@pytest.fixture
def event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc-vouchers-send')
        return Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3-vouchers-send',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
        )


@pytest.fixture
def admin_user():
    return User.objects.create_user('admin-vouchers-send@dummy.dummy', 'dummy')


@pytest.mark.django_db
def test_vouchers_send_preserves_existing_comment(event, admin_user):
    with scope(organizer=event.organizer, event=event):
        voucher = event.vouchers.create(
            code='WITHCOMMENT',
            comment='Original internal note for speaker.',
        )

        vouchers_send(
            event=event,
            vouchers=[voucher.id],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'number': 1, 'email': 'recipient@example.com', 'name': 'Test User'}],
            user=admin_user.id,
        )

        voucher.refresh_from_db()
        assert voucher.comment == (
            'Original internal note for speaker.\n\nThe voucher has been sent to recipient@example.com.'
        )


@pytest.mark.django_db
def test_vouchers_send_sets_comment_when_previously_empty(event, admin_user):
    with scope(organizer=event.organizer, event=event):
        voucher = event.vouchers.create(
            code='NOCOMMENT',
            comment='',
        )

        vouchers_send(
            event=event,
            vouchers=[voucher.id],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'number': 1, 'email': 'recipient@example.com', 'name': 'Test User'}],
            user=admin_user.id,
        )

        voucher.refresh_from_db()
        assert voucher.comment == 'The voucher has been sent to recipient@example.com.'


@pytest.mark.django_db
def test_vouchers_send_appends_multiple_sends(event, admin_user):
    with scope(organizer=event.organizer, event=event):
        voucher = event.vouchers.create(
            code='MULTISEND',
            comment='Initial note.',
            max_usages=5,
        )

        vouchers_send(
            event=event,
            vouchers=[voucher.id],
            subject='Voucher 1',
            message='Voucher: {voucher_list}',
            recipients=[{'number': 1, 'email': 'first@example.com'}],
            user=admin_user.id,
        )
        voucher.refresh_from_db()
        assert voucher.comment == 'Initial note.\n\nThe voucher has been sent to first@example.com.'

        vouchers_send(
            event=event,
            vouchers=[voucher.id],
            subject='Voucher 2',
            message='Voucher: {voucher_list}',
            recipients=[{'number': 1, 'email': 'second@example.com'}],
            user=admin_user.id,
        )
        voucher.refresh_from_db()
        assert voucher.comment == (
            'Initial note.\n\n'
            'The voucher has been sent to first@example.com.\n\n'
            'The voucher has been sent to second@example.com.'
        )
