import json

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User, Voucher
from eventyay.control.views.vouchers import VoucherRNG


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
    assert len(set(codes)) == 7
    assert all(code.startswith('EY') for code in codes)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_defaults_to_five_codes(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event))

    assert response.status_code == 200
    codes = json.loads(response.content.decode())['codes']
    assert len(codes) == 5


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_rejects_more_codes_than_the_limit(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': 1_001})

    assert response.status_code == 400


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_rejects_a_negative_number_of_codes(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': -1})

    assert response.status_code == 400


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_rejects_non_integer_num(client, env):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': 'invalid'})

    assert response.status_code == 400


@override_settings(DEBUG=True)
@pytest.mark.django_db
@pytest.mark.parametrize('num', [0, VoucherRNG.MAX_CODES])
def test_rng_accepts_count_boundaries(client, env, num):
    organizer, event, user = env
    client.force_login(user)

    response = client.get(_rng_url(organizer, event), {'num': num})

    assert response.status_code == 200
    codes = response.json()['codes']
    assert len(codes) == len(set(codes)) == num


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_accepts_maximum_prefix(client, env):
    organizer, event, user = env
    client.force_login(user)
    prefix = 'P' * VoucherRNG.get_max_prefix_length()

    response = client.get(_rng_url(organizer, event), {'num': 1, 'prefix': prefix})

    assert response.status_code == 200
    code = response.json()['codes'][0]
    assert code.startswith(prefix)
    assert len(code) == Voucher._meta.get_field('code').max_length


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_rng_rejects_prefix_one_character_over_limit(client, env, mocker):
    organizer, event, user = env
    client.force_login(user)
    prefix = 'P' * (VoucherRNG.get_max_prefix_length() + 1)
    generate = mocker.patch('eventyay.control.views.vouchers._generate_random_code')

    response = client.get(_rng_url(organizer, event), {'num': 1, 'prefix': prefix})

    assert response.status_code == 400
    generate.assert_not_called()


@override_settings(DEBUG=True)
@pytest.mark.django_db
@pytest.mark.parametrize(
    'params',
    [
        {'num': 1_001},
        {'num': -1},
        {'num': 'invalid'},
        {'num': 1_000, 'prefix': 'P' * 256},
    ],
)
def test_rng_invalid_input_does_not_generate_codes(client, env, mocker, params):
    organizer, event, user = env
    client.force_login(user)
    generate = mocker.patch('eventyay.control.views.vouchers._generate_random_code')

    response = client.get(_rng_url(organizer, event), params)

    assert response.status_code == 400
    generate.assert_not_called()


@override_settings(DEBUG=True, USE_THOUSAND_SEPARATOR=True)
@pytest.mark.django_db
@pytest.mark.parametrize('language', ['en', 'de'])
def test_bulk_page_exposes_generation_limits(client, env, language):
    organizer, event, user = env
    user.locale = language
    user.save(update_fields=['locale'])
    client.force_login(user)
    url = reverse('control:event.vouchers.bulk', kwargs={'organizer': organizer.slug, 'event': event.slug})

    response = client.get(url)

    assert response.status_code == 200
    assert response['Content-Language'].startswith(language)
    assert response.context['max_codes'] == VoucherRNG.MAX_CODES
    assert response.context['max_prefix_length'] == VoucherRNG.get_max_prefix_length()
    assert b'min="1" max="1000" step="1"' in response.content
    prefix_limit = VoucherRNG.get_max_prefix_length()
    assert f'maxlength="{prefix_limit}"'.encode() in response.content
