import json

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_view_vouchers=True, can_change_vouchers=True)
    team.members.add(user)
    team.limit_events.add(event)
    return organizer, event, user


def _rng_url(organizer, event):
    return reverse('control:event.vouchers.rng', kwargs={'organizer': organizer.slug, 'event': event.slug})


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_returns_requested_number_of_codes(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': 7, 'prefix': 'EY'})

    assert response.status_code == 200
    codes = json.loads(response.content.decode())['codes']
    assert len(codes) == 7
    assert all(code.startswith('EY') for code in codes)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_rejects_more_codes_than_the_limit(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': 100_001})

    assert response.status_code == 400
