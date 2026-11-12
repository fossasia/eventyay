import pytest
from django.core import mail as djmail
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.organizer import TeamAPIToken, TeamInvite
from eventyay.base.models.track import Track
from eventyay.base.services.team_permissions import (
    TEAM_DELEGATION_ERROR,
    can_delegate_team_permissions,
    lock_team_organizer,
)


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Dummy', slug='dummy')


@pytest.fixture
def event(organizer):
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    return event


@pytest.fixture
def admin_team(organizer):
    return Team.objects.create(organizer=organizer, can_change_teams=True, name='Admin team')


@pytest.fixture
def admin_user(admin_team):
    u = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    admin_team.members.add(u)
    return u


@pytest.fixture
def team_manager(admin_user, admin_team):
    admin_team.all_events = True
    admin_team.can_change_organizer_settings = True
    admin_team.save(update_fields=['all_events', 'can_change_organizer_settings'])
    return admin_user


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'permission',
    [
        'can_view_orders',
        'can_change_orders',
        'can_manage_bank_transfers',
        'can_manage_gift_cards',
        'can_video_moderate',
    ],
)
def test_team_manager_cannot_grant_permissions_to_own_team(client, organizer, team_manager, admin_team, permission):
    client.force_login(team_manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    prefix = f'team-{admin_team.pk}'

    response = client.post(
        url,
        {
            'team_action': 'update',
            'team_id': admin_team.pk,
            f'{prefix}-name': admin_team.name,
            f'{prefix}-all_events': 'on',
            f'{prefix}-can_change_teams': 'on',
            f'{prefix}-can_change_organizer_settings': 'on',
            f'{prefix}-{permission}': 'on',
        },
    )

    assert response.status_code == 200
    assert str(TEAM_DELEGATION_ERROR) in response.content.decode()
    admin_team.refresh_from_db()
    assert not admin_team.has_permission(permission)
    assert not admin_team.has_permission('can_view_orders')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('legacy', [False, True])
def test_team_manager_cannot_create_team_with_extra_permissions(client, organizer, team_manager, legacy):
    client.force_login(team_manager)
    teams_url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    data = {'name': 'Privileged', 'all_events': 'on', 'can_manage_gift_cards': 'on'}
    if legacy:
        url = reverse('eventyay_common:organizer.team.add', kwargs={'organizer': organizer.slug}) + '?next=' + teams_url
    else:
        url = teams_url
        data = {'team_action': 'create', **{f'team-create-{field}': value for field, value in data.items()}}

    response = client.post(url, data, follow=True)

    assert response.status_code == 200
    assert str(TEAM_DELEGATION_ERROR) in response.content.decode()
    assert not organizer.teams.filter(name='Privileged').exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('action', ['invite', 'resend', 'reissue', 'token'])
def test_team_manager_cannot_delegate_privileged_team(
    client, organizer, team_manager, action, django_capture_on_commit_callbacks
):
    client.force_login(team_manager)
    team = organizer.teams.create(name='Finance', all_events=True, can_manage_gift_cards=True)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})

    data = {'team_id': team.pk}
    if action == 'token':
        data.update({'team_action': 'tokens', f'team-{team.pk}-token-name': 'New token'})
    else:
        data['team_action'] = 'members'
        if action in ('resend', 'reissue'):
            state = TeamInvite.State.PENDING if action == 'resend' else TeamInvite.State.EXPIRED
            invite = team.invites.create(email='invitee@example.com', state=state)
            data['resend-invite'] = invite.pk
        else:
            data[f'team-{team.pk}-invite-user'] = 'invitee@example.com'

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(url, data, follow=True)

    assert response.status_code == 200
    assert str(TEAM_DELEGATION_ERROR) in response.content.decode()
    assert not djmail.outbox
    assert team.invites.open().count() == (1 if action == 'resend' else 0)
    assert not team.tokens.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_team_manager_can_grant_own_order_permission_for_covered_event(client, organizer, event, team_manager):
    orders = organizer.teams.create(name='Orders', can_change_orders=True)
    orders.limit_events.add(event)
    orders.members.add(team_manager)
    client.force_login(team_manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})

    response = client.post(
        url,
        {
            'team_action': 'create',
            'team-create-name': 'Order access',
            'team-create-limit_events': [event.pk],
            'team-create-can_change_orders': 'on',
        },
    )

    assert response.status_code == 302
    team = organizer.teams.get(name='Order access')
    assert team.permission_set() == {'can_change_orders', 'can_view_orders'}
    assert not team.all_events
    assert list(team.limit_events.all()) == [event]
    assert team.members.filter(pk=team_manager.pk).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_team_manager_cannot_remove_last_team_management_grant(client, organizer, team_manager, admin_team):
    client.force_login(team_manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    prefix = f'team-{admin_team.pk}'

    response = client.post(
        url,
        {
            'team_action': 'update',
            'team_id': admin_team.pk,
            f'{prefix}-name': admin_team.name,
            f'{prefix}-all_events': 'on',
            f'{prefix}-can_change_organizer_settings': 'on',
        },
    )

    assert response.status_code == 200
    assert 'no remaining team with the permission to change teams' in response.content.decode()
    admin_team.refresh_from_db()
    assert admin_team.can_change_teams


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_active_staff_session_can_grant_team_permissions(client, organizer):
    staff = User.objects.create_user('staff@example.com', is_staff=True)
    client.force_login(staff)
    StaffSession.objects.create(user=staff, session_key=client.session.session_key)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})

    response = client.post(
        url,
        {
            'team_action': 'create',
            'team-create-name': 'Finance',
            'team-create-all_events': 'on',
            'team-create-can_manage_gift_cards': 'on',
        },
    )

    assert response.status_code == 302
    assert organizer.teams.get(name='Finance', can_manage_gift_cards=True).members.filter(pk=staff.pk).exists()


@pytest.mark.django_db
def test_delegation_combines_permissions_only_for_covered_events(organizer, event, team_manager):
    other_event = Event.objects.create(organizer=organizer, name='Other', slug='other', date_from=now())
    orders = organizer.teams.create(name='Orders', can_change_orders=True)
    orders.limit_events.add(event)
    orders.members.add(team_manager)
    vouchers = organizer.teams.create(name='Vouchers', can_view_vouchers=True)
    vouchers.limit_events.add(event, other_event)
    vouchers.members.add(team_manager)
    changes = {'can_view_orders': True, 'can_view_vouchers': True}

    assert can_delegate_team_permissions(organizer, team_manager, changes={**changes, 'limit_events': [event]})
    assert not can_delegate_team_permissions(
        organizer, team_manager, changes={**changes, 'limit_events': [other_event]}
    )
    assert not can_delegate_team_permissions(organizer, team_manager, changes={**changes, 'all_events': True})


@pytest.mark.django_db
def test_delegation_preserves_existing_grants_without_allowing_scope_expansion(organizer, event, team_manager):
    finance = organizer.teams.create(name='Finance', can_manage_bank_transfers=True)
    finance.limit_events.add(event)
    other_event = Event.objects.create(organizer=organizer, name='Other', slug='other', date_from=now())

    assert can_delegate_team_permissions(organizer, team_manager, team=finance, changes={'name': 'Banking'})
    assert can_delegate_team_permissions(
        organizer, team_manager, team=finance, changes={'can_manage_bank_transfers': False}
    )
    assert not can_delegate_team_permissions(
        organizer, team_manager, team=finance, changes={'limit_events': [event, other_event]}
    )
    assert not can_delegate_team_permissions(organizer, team_manager, team=finance, changes={'all_events': True})


@pytest.mark.django_db
def test_delegation_cannot_expand_reviewer_tracks_or_speaker_visibility(organizer, event, team_manager):
    with scope(event=event):
        allowed = Track.objects.create(event=event, name='Allowed')
        other = Track.objects.create(event=event, name='Other')
    reviewers = organizer.teams.create(name='Reviewers', is_reviewer=True, force_hide_speaker_names=True)
    reviewers.limit_events.add(event)
    reviewers.limit_tracks.add(allowed)
    reviewers.members.add(team_manager)
    grant = {'is_reviewer': True, 'limit_events': [event], 'limit_tracks': [allowed], 'force_hide_speaker_names': True}

    assert can_delegate_team_permissions(organizer, team_manager, changes=grant)
    assert not can_delegate_team_permissions(organizer, team_manager, changes={**grant, 'limit_tracks': []})
    assert not can_delegate_team_permissions(organizer, team_manager, changes={**grant, 'limit_tracks': [other]})
    assert not can_delegate_team_permissions(
        organizer, team_manager, changes={**grant, 'force_hide_speaker_names': False}
    )
    assert not can_delegate_team_permissions(organizer, team_manager, team=reviewers, changes={'limit_tracks': []})
    assert not can_delegate_team_permissions(
        organizer, team_manager, team=reviewers, changes={'force_hide_speaker_names': False}
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('permission', 'restriction'),
    [('is_reviewer', 'force_hide_speaker_emails'), ('is_exhibition_reviewer', 'hide_exhibition_applicant_emails')],
)
def test_delegation_cannot_remove_email_visibility_restriction(organizer, team_manager, permission, restriction):
    grant = {'all_events': True, permission: True, restriction: True}
    team = organizer.teams.create(name='Reviewers', **grant)
    team.members.add(team_manager)

    assert can_delegate_team_permissions(organizer, team_manager, changes=grant)
    assert not can_delegate_team_permissions(organizer, team_manager, changes={**grant, restriction: False})
    assert not can_delegate_team_permissions(organizer, team_manager, team=team, changes={restriction: False})


@pytest.mark.django_db
def test_delegation_cannot_expand_teamshifts_roles_or_email_visibility(organizer, event, team_manager):
    grant = {
        'limit_events': [event],
        'teamshifts_role': 'lead',
        'limit_teamshifts_roles': [1],
        'hide_teamshifts_emails': True,
    }
    assert not can_delegate_team_permissions(organizer, team_manager, changes=grant)

    team = organizer.teams.create(
        name='TeamShifts lead', teamshifts_role='lead', limit_teamshifts_roles=[1], hide_teamshifts_emails=True
    )
    team.limit_events.add(event)
    team.members.add(team_manager)

    assert can_delegate_team_permissions(organizer, team_manager, changes=grant)
    assert not can_delegate_team_permissions(organizer, team_manager, changes={**grant, 'all_teamshifts_roles': True})
    assert not can_delegate_team_permissions(
        organizer, team_manager, changes={**grant, 'teamshifts_role': 'coordinator'}
    )
    assert not can_delegate_team_permissions(
        organizer, team_manager, team=team, changes={'limit_teamshifts_roles': [2]}
    )
    assert not can_delegate_team_permissions(
        organizer, team_manager, team=team, changes={'hide_teamshifts_emails': False}
    )


@pytest.mark.django_db
@pytest.mark.parametrize('credential', ['membership', 'token'])
def test_delegation_locks_credential_used_for_grant(organizer, admin_team, admin_user, credential):
    admin_team.can_manage_gift_cards = True
    admin_team.save(update_fields=['can_manage_gift_cards'])
    if credential == 'token':
        actor = admin_team.tokens.create(name='Manager token')
        credential_table = TeamAPIToken._meta.db_table
    else:
        actor = admin_user
        credential_table = Team.members.through._meta.db_table

    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        lock_team_organizer(organizer.pk)
        assert can_delegate_team_permissions(organizer, actor, changes={'can_manage_gift_cards': True}, lock=True)

    grant_query = next(query['sql'] for query in queries if f'INNER JOIN "{credential_table}"' in query['sql'])
    assert grant_query.endswith('FOR NO KEY UPDATE')


@pytest.mark.django_db
def test_list_of_teams(event, admin_user, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    resp = client.get('/control/organizer/dummy/teams')
    assert 'Admin team' in resp.content.decode()


@pytest.mark.django_db
def test_team_detail_view(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    resp = client.get('/control/organizer/dummy/team/{}/'.format(admin_team.pk))
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()


@pytest.mark.django_db
def test_team_add_user(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    u = User.objects.create_user('dummy2@dummy.dummy', 'dummy')

    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'user': u.email},
        follow=True,
    )
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()
    assert u.email in resp.content.decode()
    with scopes_disabled():
        assert u in admin_team.members.all()


@pytest.mark.django_db
def test_team_create_invite(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    djmail.outbox = []

    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'user': 'foo@example.org'},
        follow=True,
    )
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()
    assert 'foo@example.org' in resp.content.decode()
    with scopes_disabled():
        assert admin_team.invites.first().email == 'foo@example.org'
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_team_create_token(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    djmail.outbox = []

    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'name': 'Test token'},
        follow=True,
    )
    assert 'Test token' in resp.content.decode()
    with scopes_disabled():
        assert admin_team.tokens.first().name == 'Test token'
        assert admin_team.tokens.first().token in resp.content.decode()


@pytest.mark.django_db
def test_team_remove_token(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    with scopes_disabled():
        tk = admin_team.tokens.create(name='Test token')
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-token': str(tk.pk)},
        follow=True,
    )
    assert tk.token not in resp.content.decode()
    assert 'Test token' in resp.content.decode()
    tk.refresh_from_db()
    assert not tk.active


@pytest.mark.django_db
def test_team_resend_invite(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    djmail.outbox = []

    inv = admin_team.invites.create(email='foo@example.org')
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'resend-invite': str(inv.pk)},
        follow=True,
    )
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()
    assert 'foo@example.org' in resp.content.decode()
    assert len(djmail.outbox) == 1


@pytest.mark.django_db
def test_team_revoke_invite(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    with scopes_disabled():
        inv = admin_team.invites.create(email='foo@example.org')
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-invite': str(inv.pk)},
        follow=True,
    )
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()
    with scopes_disabled():
        assert not admin_team.invites.exists()


@pytest.mark.django_db
def test_team_remove_user(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    u = User.objects.create_user('dummy2@dummy.dummy', 'dummy')
    with scopes_disabled():
        admin_team.members.add(u)

    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-member': u.pk},
        follow=True,
    )
    assert 'Admin team' in resp.content.decode()
    assert admin_user.email in resp.content.decode()
    with scopes_disabled():
        assert u not in admin_team.members.all()


@pytest.mark.django_db
def test_team_remove_last_admin(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-member': admin_user.pk},
        follow=True,
    )
    assert 'alert-danger' in resp.content.decode()
    with scopes_disabled():
        assert admin_user in admin_team.members.all()

    t2 = Team.objects.create(organizer=event.organizer, name='Admin team 2')
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-member': admin_user.pk},
        follow=True,
    )
    assert 'alert-danger' in resp.content.decode()
    with scopes_disabled():
        assert admin_user in admin_team.members.all()

    t2.members.add(admin_user)
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-member': admin_user.pk},
        follow=True,
    )
    assert 'alert-danger' in resp.content.decode()
    with scopes_disabled():
        assert admin_user in admin_team.members.all()

    t2.can_change_teams = True
    t2.save()
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'remove-member': admin_user.pk},
        follow=True,
    )
    assert 'alert-danger' not in resp.content.decode()
    with scopes_disabled():
        assert admin_user not in admin_team.members.all()


@pytest.mark.django_db
def test_create_team(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    client.post(
        '/control/organizer/dummy/team/add',
        {
            'name': 'Foo',
            'can_create_events': 'on',
            'limit_events': str(event.pk),
            'can_change_event_settings': 'on',
        },
        follow=True,
    )
    with scopes_disabled():
        t = Team.objects.last()
        assert t.can_change_event_settings
        assert t.can_create_events
        assert not t.can_change_organizer_settings
        assert list(t.limit_events.all()) == [event]
        assert list(t.members.all()) == [admin_user]


@pytest.mark.django_db
def test_create_team_validation_failure_keeps_form_open(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    resp = client.post(
        '/control/organizer/dummy/teams',
        {
            'team_action': 'create',
            'team-create-name': 'Invalid Team',
            'team-create-all_events': 'on',
        },
        follow=True,
    )
    content = resp.content.decode()
    assert 'Something went wrong' in content
    assert 'Please pick at least one permission for this team!' in content
    assert 'id="create-team-form" class="collapse in"' in content


@pytest.mark.django_db
def test_create_team_success_collapses_form(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    resp = client.post(
        '/control/organizer/dummy/teams',
        {
            'team_action': 'create',
            'team-create-name': 'New Team',
            'team-create-all_events': 'on',
            'team-create-can_create_events': 'on',
        },
        follow=True,
    )
    content = resp.content.decode()
    assert 'The team has been created.' in content
    assert 'id="create-team-form" class="collapse in"' not in content
    assert 'id="create-team-form" class="collapse"' in content


@pytest.mark.django_db
def test_update_team(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    client.post(
        '/control/organizer/dummy/team/{}/edit'.format(admin_team.pk),
        {
            'name': 'Admin',
            'can_change_teams': 'on',
            'limit_events': str(event.pk),
            'can_change_event_settings': 'on',
        },
        follow=True,
    )
    admin_team.refresh_from_db()
    assert admin_team.can_change_event_settings
    assert not admin_team.can_change_organizer_settings
    with scopes_disabled():
        assert list(admin_team.limit_events.all()) == [event]


@pytest.mark.django_db
def test_update_last_team_to_be_no_admin(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    resp = client.post(
        '/control/organizer/dummy/team/{}/edit'.format(admin_team.pk),
        {'name': 'Admin', 'can_change_event_settings': 'on'},
        follow=True,
    )
    assert 'alert-danger' in resp.content.decode()


@pytest.mark.django_db
def test_remove_team(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    with scopes_disabled():
        t2 = Team.objects.create(organizer=event.organizer, name='Admin team 2')
    resp = client.post('/control/organizer/dummy/team/{}/delete'.format(t2.pk), {}, follow=True)
    with scopes_disabled():
        assert Team.objects.count() == 1
    assert 'alert-success' in resp.content.decode()


@pytest.mark.django_db
def test_remove_last_admin_team(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')

    resp = client.post('/control/organizer/dummy/team/{}/delete'.format(admin_team.pk), {}, follow=True)
    with scopes_disabled():
        assert Team.objects.count() == 1
    assert 'alert-danger' in resp.content.decode()


@pytest.mark.django_db
def test_resend_invalid_invite(event, admin_user, admin_team, client):
    client.login(email='dummy@dummy.dummy', password='dummy')
    djmail.outbox = []

    with scopes_disabled():
        inv = admin_team.invites.create(email='foo@example.org')
    resp = client.post(
        '/control/organizer/dummy/team/{}/'.format(admin_team.pk),
        {'resend-invite': inv.pk + 1},
        follow=True,
    )
    assert b'alert-danger' in resp.content
    assert b'Invalid invite selected.' in resp.content
    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_invite_invalid_token(event, admin_team, client):
    with scopes_disabled():
        i = admin_team.invites.create(email='foo@bar.com')
    resp = client.get('/control/invite/foo{}bar'.format(i.token), follow=True)
    assert b'alert-danger' in resp.content
    assert b'invalid link' in resp.content


@pytest.mark.django_db
def test_invite_existing_team_member(event, admin_team, client):
    u = User.objects.create_user('dummy2@dummy.dummy', 'dummy')
    with scopes_disabled():
        admin_team.members.add(u)
        client.login(email='dummy2@dummy.dummy', password='dummy')
        i = admin_team.invites.create(email='foo@bar.com')
    resp = client.get('/control/invite/{}'.format(i.token), follow=True)
    assert b'alert-danger' in resp.content
    assert b'already are part of' in resp.content


@pytest.mark.django_db
def test_invite_authenticated(event, admin_team, client):
    u = User.objects.create_user('dummy2@dummy.dummy', 'dummy')
    client.login(email='dummy2@dummy.dummy', password='dummy')
    with scopes_disabled():
        i = admin_team.invites.create(email='foo@bar.com')
    resp = client.get('/control/invite/{}'.format(i.token), follow=True)
    assert b'alert-success' in resp.content
    with scopes_disabled():
        assert u in admin_team.members.all()
        assert not admin_team.invites.exists()


@pytest.mark.django_db
def test_invite_new_user(event, admin_team, client):
    with scopes_disabled():
        i = admin_team.invites.create(email='foo@bar.com')
    resp = client.get('/control/invite/{}'.format(i.token), follow=True)
    assert b'<form' in resp.content
    resp = client.post(
        '/control/invite/{}'.format(i.token),
        {
            'email': 'dummy@example.org',
            'password': 'asdsdgfgjh',
            'password_repeat': 'asdsdgfgjh',
        },
        follow=True,
    )

    assert b'alert-success' in resp.content
    with scopes_disabled():
        assert admin_team.members.filter(email='dummy@example.org').exists()
        assert not admin_team.invites.exists()
