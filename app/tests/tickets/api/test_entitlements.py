import pytest
from django.dispatch import Signal

from eventyay.base import entitlements


@pytest.fixture
def api_policy(monkeypatch):
    signal = Signal()
    monkeypatch.setattr(entitlements, 'entitlement_check', signal)
    denied = set()
    calls = []

    def receiver(sender, capability, event, **kwargs):
        calls.append((sender, capability, event))
        return capability not in denied

    signal.connect(receiver, weak=False)
    return denied, calls


@pytest.mark.django_db
@pytest.mark.parametrize('method,capability', [('get', 'api.read'), ('head', 'api.read'), ('post', 'api.write')])
def test_team_token_api_access_uses_plan(token_client, team, organizer, event, api_policy, method, capability):
    team.can_change_items = True
    team.save()
    denied, calls = api_policy
    url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/categories/'
    kwargs = {'data': {'name': 'Test Category'}, 'format': 'json'} if method == 'post' else {}
    assert getattr(token_client, method)(url, **kwargs).status_code != 403
    denied.add(capability)
    assert getattr(token_client, method)(url, **kwargs).status_code == 403
    assert calls[-1] == (organizer, capability, event)
    denied.clear()
    assert getattr(token_client, method)(url, **kwargs).status_code != 403


@pytest.mark.django_db
def test_plan_api_flags_do_not_block_browser_management(user_client, organizer, event, api_policy):
    api_policy[0].update(('api.read', 'api.write'))
    url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/categories/'
    assert user_client.get(url).status_code == 200
    assert not api_policy[1]


@pytest.mark.django_db
def test_plan_allowance_does_not_grant_missing_team_permissions(token_client, team, organizer, event, api_policy):
    team.can_change_items = False
    team.save()
    url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/categories/'
    assert token_client.post(url, {'name': 'Test Category'}, format='json').status_code == 403


@pytest.mark.django_db
def test_other_organizer_plan_cannot_block_event_api(token_client, organizer, event, api_policy):
    signal = entitlements.entitlement_check

    def deny_other_organizer(sender, **kwargs):
        return sender.pk == organizer.pk

    signal.connect(deny_other_organizer, weak=False)
    url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/categories/'
    assert token_client.get(url).status_code == 200


@pytest.mark.django_db
def test_organizer_endpoints_enforce_api_read_for_tokens(token_client, organizer, api_policy):
    denied, _ = api_policy
    list_url = '/api/v1/organizers/'
    detail_url = f'/api/v1/organizers/{organizer.slug}/'

    assert token_client.get(list_url).status_code == 200
    assert token_client.get(detail_url).status_code == 200

    denied.add('api.read')
    assert token_client.get(list_url).status_code == 403
    assert token_client.get(detail_url).status_code == 403

    denied.clear()
    assert token_client.get(list_url).status_code == 200
    assert token_client.get(detail_url).status_code == 200


@pytest.mark.django_db
def test_organizer_endpoints_unaffected_for_browser_sessions(user_client, organizer, api_policy):
    api_policy[0].add('api.read')
    assert user_client.get('/api/v1/organizers/').status_code == 200
    assert user_client.get(f'/api/v1/organizers/{organizer.slug}/').status_code == 200


@pytest.mark.django_db
def test_organizer_list_filters_denied_organizer_for_user_token(client, user, organizer, api_policy):
    from eventyay.base.models import Organizer

    other_orga = Organizer.objects.create(name='Other Orga', slug='other-orga')
    team = organizer.teams.create(name='Team 1', can_change_organizer_settings=True)
    team.members.add(user)
    team2 = other_orga.teams.create(name='Team 2', can_change_organizer_settings=True)
    team2.members.add(user)

    token = user.api_tokens.create(name='User Token')
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.token}')

    res = client.get('/api/v1/organizers/')
    assert res.status_code == 200
    slugs = {item['slug'] for item in res.data['results']}
    assert organizer.slug in slugs
    assert other_orga.slug in slugs

    # Deny api.read for other_orga only
    signal = entitlements.entitlement_check

    def selective_policy(sender, capability, **kwargs):
        if sender.pk == other_orga.pk and capability == 'api.read':
            return False
        return True

    signal.connect(selective_policy, weak=False)

    res = client.get('/api/v1/organizers/')
    assert res.status_code == 200
    slugs = {item['slug'] for item in res.data['results']}
    assert organizer.slug in slugs
    assert other_orga.slug not in slugs


@pytest.mark.django_db
def test_object_permission_uses_request_organizer_for_users(organizer, event, api_policy):
    from types import SimpleNamespace

    from eventyay.api.auth.permission import EventPermission
    from eventyay.base.models import Organizer, TeamAPIToken, User

    denied, calls = api_policy
    denied.add('api.read')
    other = Organizer.objects.create(name='Other', slug='other')
    member = User(email='member@example.org')
    member.event = event
    event.organizer = other
    request = SimpleNamespace(method='GET', auth=TeamAPIToken(), organizer=organizer)

    assert not EventPermission().has_object_permission(request, None, member)
    assert calls[-1][0] is organizer
