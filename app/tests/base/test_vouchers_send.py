from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, User, Voucher
from eventyay.base.services.vouchers import vouchers_send


@pytest.fixture
def event(db):
    organizer = Organizer.objects.create(name='Org', slug='sendorg')
    return Event.objects.create(
        organizer=organizer,
        name='Event',
        slug='sendevent',
        date_from=timezone.now() + timedelta(days=10),
        currency='EUR',
    )


@pytest.fixture
def user(db):
    return User.objects.create_user('organizer@example.org', 'secret')


def _send(event, user, voucher):
    with scopes_disabled(), mock.patch('eventyay.base.services.vouchers.mail'):
        vouchers_send(
            event=event,
            vouchers=[voucher.pk],
            subject='Your voucher',
            message='Hello {voucher_list}',
            recipients=[{'email': 'guest@example.org', 'name': 'Guest', 'number': 1}],
            user=user.pk,
        )
    with scopes_disabled():
        voucher.refresh_from_db()


def test_send_adds_note_to_empty_comment(event, user):
    with scopes_disabled():
        voucher = Voucher.objects.create(event=event)
    _send(event, user, voucher)
    assert voucher.comment == 'The voucher has been sent to guest@example.org.'


def test_send_keeps_existing_comment(event, user):
    with scopes_disabled():
        voucher = Voucher.objects.create(event=event, comment='Reserved for speakers')
    _send(event, user, voucher)
    assert voucher.comment == 'Reserved for speakers\n\nThe voucher has been sent to guest@example.org.'
