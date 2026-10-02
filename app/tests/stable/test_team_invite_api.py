import pytest
from django.core import mail as djmail
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Team
from eventyay.helpers.urls import build_absolute_uri


@pytest.fixture
@scopes_disabled()
def team(organizer):
    return Team.objects.create(organizer=organizer, name='Test-Team', can_change_teams=True)


@pytest.fixture
@scopes_disabled()
def token_client(team):
    client = APIClient()
    token = team.tokens.create(name='Foo')
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)
    return client


@pytest.mark.django_db
def test_invite_new_user_sends_invitation_link(token_client, organizer, team, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        resp = token_client.post(
            f'/api/v1/organizers/{organizer.slug}/teams/{team.pk}/invites/',
            {'email': 'newperson@example.org'},
        )

    assert resp.status_code == 201
    with scopes_disabled():
        invite = team.invites.get()
    assert invite.email == 'newperson@example.org'
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['newperson@example.org']
    invite_url = build_absolute_uri('eventyay_common:auth.invite', kwargs={'token': invite.token})
    assert invite_url in djmail.outbox[0].body
