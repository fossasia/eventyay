"""Tests for the schedule-public endpoint and the production SECRET_KEY guard.

The endpoint authorizes with an HS256 JWT signed with SECRET_KEY. The token names a user
but not an event, so the view must check that user's permission on the event in the URL.
"""
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import Team, User
from eventyay.config.secret_key import ensure_secret_key_is_private


def make_token(email, has_perms='base.edit_schedule'):
    payload = {
        'email': email,
        'has_perms': has_perms,
        'exp': datetime.now(UTC) + timedelta(hours=1),
        'iat': datetime.now(UTC),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def post(client, organizer, event, token, is_show_schedule=True):
    return client.post(
        f'/api/v1/{organizer.slug}/{event.slug}/schedule-public',
        {'is_show_schedule': is_show_schedule},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )


@pytest.fixture
@scopes_disabled()
def outsider(organizer, event2):
    """A user whose only team is limited to event2."""
    user = User.objects.create_user('outsider@example.com', 'outsider')
    team = Team.objects.create(organizer=organizer, name='Other event', can_change_event_settings=True)
    team.limit_events.add(event2)
    team.members.add(user)
    return user


@pytest.mark.django_db
def test_team_member_can_toggle_schedule(client, organizer, event, team, user):
    with scopes_disabled():
        team.all_events = True
        team.save()
        team.members.add(user)

    resp = post(client, organizer, event, make_token(user.email))

    assert resp.status_code == 200
    event.refresh_from_db()
    assert event.feature_flags['show_schedule'] is True


@pytest.mark.django_db
def test_user_without_event_permission_is_rejected(client, organizer, event, outsider):
    before = event.feature_flags.get('show_schedule')

    resp = post(client, organizer, event, make_token(outsider.email), is_show_schedule=not before)

    assert resp.status_code == 403
    event.refresh_from_db()
    # The rejected request must not have changed the flag.
    assert event.feature_flags.get('show_schedule') == before


@pytest.mark.django_db
def test_user_without_any_team_is_rejected(client, organizer, event):
    User.objects.create_user('nobody@example.com', 'nobody')
    before = event.feature_flags.get('show_schedule')

    resp = post(client, organizer, event, make_token('nobody@example.com'), is_show_schedule=not before)

    assert resp.status_code == 403
    event.refresh_from_db()
    assert event.feature_flags.get('show_schedule') == before


@pytest.mark.django_db
def test_token_without_schedule_permission_is_rejected(client, organizer, event, team, user):
    with scopes_disabled():
        team.all_events = True
        team.save()
        team.members.add(user)

    resp = post(client, organizer, event, make_token(user.email, has_perms='something.else'))

    assert resp.status_code == 403


@pytest.mark.parametrize('key', ['please-give-one-in-secret-file', 'CHANGEME'])
def test_production_refuses_public_secret_key(key):
    with override_settings(IS_PRODUCTION=True, SECRET_KEY=key):
        with pytest.raises(ImproperlyConfigured):
            ensure_secret_key_is_private()


def test_production_accepts_private_secret_key():
    with override_settings(IS_PRODUCTION=True, SECRET_KEY='a-real-private-key-' + 'x' * 40):
        ensure_secret_key_is_private()


def test_non_production_allows_placeholder_secret_key():
    with override_settings(IS_PRODUCTION=False, SECRET_KEY='please-give-one-in-secret-file'):
        ensure_secret_key_is_private()
