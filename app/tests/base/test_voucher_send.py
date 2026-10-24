import datetime

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User
from eventyay.base.services.vouchers import vouchers_send


@pytest.fixture
def env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc-vouchers-send')
        event = Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.UTC),
        )
        user = User.objects.create_user('test@example.com', 'test')
        v1 = event.vouchers.create(comment='Reserved for speaker', code='TEST1')
        v2 = event.vouchers.create(comment='', code='TEST2')
        return event, user, v1, v2


@pytest.mark.django_db
def test_vouchers_send_preserves_existing_comment(env):
    event, user, v1, v2 = env
    with scopes_disabled():
        vouchers_send(
            event=event,
            vouchers=[v1.pk],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'email': 'speaker@example.com', 'number': 1}],
            user=user.pk,
        )
        v1.refresh_from_db()
        assert v1.comment == 'Reserved for speaker\n\nThe voucher has been sent to speaker@example.com.'


@pytest.mark.django_db
def test_vouchers_send_sets_comment_when_empty(env):
    event, user, v1, v2 = env
    with scopes_disabled():
        vouchers_send(
            event=event,
            vouchers=[v2.pk],
            subject='Your voucher',
            message='Here is your voucher: {voucher_list}',
            recipients=[{'email': 'attendee@example.com', 'number': 1}],
            user=user.pk,
        )
        v2.refresh_from_db()
        assert v2.comment == 'The voucher has been sent to attendee@example.com.'
