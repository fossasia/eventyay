from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import Team, TeamInvite, User
from eventyay.base.services.teams import TeamInviteError, invite_to_team, process_team_invites


@pytest.fixture(autouse=True)
def clear_periodic_cache():
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
@scopes_disabled()
def helpers_team(organizer, event):
    team = Team.objects.create(organizer=organizer, name='Helpers', can_change_teams=True)
    team.limit_events.add(event)
    return team


@pytest.fixture
def invitee(db):
    return User.objects.create_user(email='invitee@example.org', password='invitepass123', locale='en')


def _invite(team, email, django_capture_on_commit_callbacks):
    with scopes_disabled(), django_capture_on_commit_callbacks(execute=True):
        return invite_to_team(team, email)


def _invite_url(invite):
    return reverse('eventyay_common:auth.invite', kwargs={'token': invite.token})


@pytest.mark.django_db
def test_inviting_existing_user_creates_pending_invite_without_membership(
    helpers_team, invitee, django_capture_on_commit_callbacks
):
    invite = _invite(helpers_team, 'INVITEE@example.org', django_capture_on_commit_callbacks)

    assert invite.user == invitee
    assert invite.state == TeamInvite.State.PENDING
    assert invite.expires - invite.created == timedelta(hours=48)
    assert not helpers_team.members.filter(pk=invitee.pk).exists()
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].subject == 'Invitation to join the “Helpers” team for “Test Event”'
    assert 'accept or decline the invitation' in djmail.outbox[0].body
    assert invite.invitation_url in djmail.outbox[0].body


@pytest.mark.django_db
def test_inviting_new_email_sends_account_invitation(helpers_team, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, 'newperson@example.org', django_capture_on_commit_callbacks)

    assert invite.user is None
    assert djmail.outbox[0].subject == 'Invitation to join eventyay and the “Helpers” team for “Test Event”'
    assert 'Creating an account does not automatically accept the team invitation' in djmail.outbox[0].body


@pytest.mark.django_db
def test_api_invite_for_existing_user_does_not_add_member(
    organizer, helpers_team, invitee, django_capture_on_commit_callbacks, allow_all_entitlements
):
    client = APIClient()
    with scopes_disabled():
        token = helpers_team.tokens.create(name='Foo')
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f'/api/v1/organizers/{organizer.slug}/teams/{helpers_team.pk}/invites/',
            {'email': invitee.email},
        )

    assert response.status_code == 201
    with scopes_disabled():
        assert not helpers_team.members.filter(pk=invitee.pk).exists()
        assert helpers_team.invites.get().user == invitee


@pytest.mark.django_db
def test_duplicate_open_invite_is_rejected(helpers_team, invitee, django_capture_on_commit_callbacks):
    _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)

    with scopes_disabled(), pytest.raises(TeamInviteError):
        invite_to_team(helpers_team, invitee.email)


@pytest.mark.django_db
def test_recipient_accepts_invitation(client, helpers_team, invitee, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    client.force_login(invitee)

    response = client.get(_invite_url(invite))
    assert response.status_code == 200
    assert 'Accept invitation' in response.content.decode()

    response = client.post(_invite_url(invite), {'action': 'accept'})

    assert response.status_code == 302
    with scopes_disabled():
        assert helpers_team.members.filter(pk=invitee.pk).exists()
        invite = TeamInvite.all_objects.get(pk=invite.pk)
        assert invite.state == TeamInvite.State.ACCEPTED
        assert not helpers_team.invites.exists()
    assert client.get(_invite_url(invite)).status_code == 410


@pytest.mark.django_db
def test_recipient_declines_invitation(client, helpers_team, invitee, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    client.force_login(invitee)

    client.post(_invite_url(invite), {'action': 'decline'})

    invite.refresh_from_db()
    assert invite.state == TeamInvite.State.DECLINED
    assert not helpers_team.members.filter(pk=invitee.pk).exists()


@pytest.mark.django_db
def test_other_account_cannot_accept_invitation(client, helpers_team, invitee, user, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    client.force_login(user)

    assert client.get(_invite_url(invite)).status_code == 403
    assert client.post(_invite_url(invite), {'action': 'accept'}).status_code == 403

    invite.refresh_from_db()
    assert invite.state == TeamInvite.State.PENDING
    assert not helpers_team.members.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_expired_invitation_cannot_be_accepted(client, helpers_team, invitee, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    TeamInvite.objects.filter(pk=invite.pk).update(expires=now() - timedelta(minutes=1))
    client.force_login(invitee)

    response = client.post(_invite_url(invite), {'action': 'accept'})

    assert response.status_code == 410
    assert 'has expired' in response.content.decode()
    assert not helpers_team.members.filter(pk=invitee.pk).exists()


@pytest.mark.django_db
def test_registering_through_invitation_does_not_join_team(client, helpers_team, django_capture_on_commit_callbacks):
    invite = _invite(helpers_team, 'newperson@example.org', django_capture_on_commit_callbacks)

    response = client.post(
        _invite_url(invite),
        {
            'email': 'someone-else@example.org',
            'password': 'Sup3r-Secret-Passw0rd!',
            'password_repeat': 'Sup3r-Secret-Passw0rd!',
        },
    )

    assert response.status_code == 302
    new_user = User.objects.get(email='newperson@example.org')
    assert not User.objects.filter(email='someone-else@example.org').exists()
    invite.refresh_from_db()
    assert invite.user == new_user
    assert invite.state == TeamInvite.State.PENDING
    assert not helpers_team.members.filter(pk=new_user.pk).exists()
    assert 'Accept invitation' in client.get(_invite_url(invite)).content.decode()


@pytest.mark.django_db
def test_dashboard_lists_pending_invitations(client, helpers_team, invitee, django_capture_on_commit_callbacks):
    _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    client.force_login(invitee)

    response = client.get(reverse('eventyay_common:dashboard'))

    assert 'You have been invited to join “Helpers” for “Test Event”.' in response.content.decode()


@pytest.mark.django_db
def test_dashboard_lists_unbound_invite_for_matching_email(client, helpers_team, invitee, user):
    with scopes_disabled():
        helpers_team.invites.create(email='Invitee@example.org', user=None)
        helpers_team.invites.create(email=invitee.email, user=user)
    client.force_login(invitee)

    response = client.get(reverse('eventyay_common:dashboard'))

    assert response.content.decode().count('You have been invited to join “Helpers” for “Test Event”.') == 1


@pytest.mark.django_db
def test_periodic_task_sends_one_reminder_and_expires_invites(
    helpers_team, invitee, django_capture_on_commit_callbacks
):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    TeamInvite.objects.filter(pk=invite.pk).update(created=now() - timedelta(hours=25))
    djmail.outbox.clear()

    process_team_invites(sender=None)
    from django.core.cache import cache

    cache.clear()
    process_team_invites(sender=None)

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].subject == 'Reminder: Invitation to join the “Helpers” team for “Test Event”'

    TeamInvite.objects.filter(pk=invite.pk).update(expires=now() - timedelta(minutes=1))
    cache.clear()
    process_team_invites(sender=None)

    invite.refresh_from_db()
    assert invite.state == TeamInvite.State.EXPIRED
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organizer_can_send_new_invitation_after_expiry(
    organizer_client, organizer, helpers_team, invitee, django_capture_on_commit_callbacks
):
    invite = _invite(helpers_team, invitee.email, django_capture_on_commit_callbacks)
    old_token = invite.token
    TeamInvite.objects.filter(pk=invite.pk).update(state=TeamInvite.State.EXPIRED)
    djmail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        organizer_client.post(
            reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug}),
            {'team_action': 'members', 'team_id': helpers_team.pk, 'resend-invite': invite.pk},
        )

    invite.refresh_from_db()
    assert invite.state == TeamInvite.State.PENDING
    assert invite.token != old_token
    assert invite.expires > now() + timedelta(hours=47)
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organizer_team_page_shows_invite_states(organizer_client, organizer, helpers_team, invitee):
    with scopes_disabled():
        helpers_team.invites.create(
            email='expired@example.org',
            state=TeamInvite.State.EXPIRED,
            expires=now() - timedelta(hours=1),
        )
        helpers_team.invites.create(email='declined@example.org', state=TeamInvite.State.DECLINED)
        helpers_team.invites.create(
            email=invitee.email,
            user=invitee,
            reminder_sent=now(),
        )
        accepted = User.objects.create_user(email='accepted@example.org', password='acceptedpass123')
        helpers_team.members.add(accepted)
        TeamInvite.all_objects.create(
            team=helpers_team,
            email=accepted.email,
            user=accepted,
            state=TeamInvite.State.ACCEPTED,
        )
        accepted.email = 'renamed@example.org'
        accepted.save(update_fields=['email'])
        other = User.objects.create_user(email='accepted@example.org', password='otherpass123')
        helpers_team.members.add(other)

    response = organizer_client.get(
        reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug}),
        {'team': helpers_team.pk, 'panel': 'members'},
    )
    content = response.content.decode()

    assert 'label-warning' in content
    assert 'Expired' in content
    assert 'label-danger' in content
    assert 'Declined' in content
    assert 'Follow-up reminder sent' in content
    assert 'label-success' in content
    renamed_row = content.split('renamed@example.org', 1)[1].split('</tr>', 1)[0]
    assert 'Accepted' in renamed_row
    other_row = content.split('accepted@example.org', 1)[1].split('</tr>', 1)[0]
    assert 'Accepted' not in other_row


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_message_center_lists_read_only_team_invitation_templates(organizer_client, organizer, event):
    kwargs = {'organizer': organizer.slug, 'event': event.slug}
    listing = organizer_client.get(reverse('control:event.mail.templates', kwargs=kwargs)).content.decode()
    assert 'Team invitation for an existing eventyay user' in listing
    assert 'Team invitation for a person without an eventyay account' in listing
    assert 'Pending team invitation reminder' in listing

    detail_url = reverse('control:event.mail.templates.team', kwargs={**kwargs, 'template_key': 'team-invitation'})
    detail = organizer_client.get(detail_url)
    content = detail.content.decode()
    assert detail.status_code == 200
    assert 'cannot be edited or deleted' in content
    assert '{team}' in content
    assert 'Invitation to join the “Program committee” team for “Test Event”' in content
    assert organizer_client.post(detail_url).status_code == 405
