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
