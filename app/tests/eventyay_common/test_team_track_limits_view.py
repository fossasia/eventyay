import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, LogEntry, Organizer, Team, Track, User


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Track View Org', slug='trackview')


@pytest.fixture
def tracks(organizer):
    """One track in each of two events."""
    first = Event.objects.create(organizer=organizer, name='First Event', slug='first', date_from=now())
    second = Event.objects.create(organizer=organizer, name='Second Event', slug='second', date_from=now())
    with scopes_disabled():
        return (
            Track.objects.create(event=first, name='Alpha', color='#aa0000'),
            Track.objects.create(event=second, name='Beta', color='#00aa00'),
        )


@pytest.fixture
def team(organizer):
    return Team.objects.create(organizer=organizer, name='Reviewers', all_events=True, is_reviewer=True)


@pytest.fixture
def admin_client(client, organizer, settings):
    # The control middleware redirects organizer pages to SITE_URL unless DEBUG is on.
    settings.DEBUG = True
    admin_team = Team.objects.create(organizer=organizer, name='Admins', all_events=True, can_change_teams=True)
    user = User.objects.create_user('admin@example.org', 'secret')
    admin_team.members.add(user)
    client.login(email='admin@example.org', password='secret')
    return client


def _teams_url(organizer):
    return f'/common/organizer/{organizer.slug}/teams'


def _update_team(client, organizer, team, **fields):
    """Post the team permissions form the way the unified organizer page does (prefixed fields)."""
    prefix = f'team-{team.pk}-'
    data = {'name': 'Reviewers', 'all_events': 'on', 'is_reviewer': 'on', **fields}
    payload = {prefix + key: value for key, value in data.items() if value is not None}
    payload.update({'team_action': 'update', 'team_id': team.pk})
    return client.post(_teams_url(organizer), payload)


@pytest.mark.django_db
def test_permissions_page_shows_grouped_track_checklist(admin_client, organizer, team, tracks):
    response = admin_client.get(_teams_url(organizer), {'section': 'permissions', 'team': team.pk})
    html = response.content.decode()

    assert f'name="team-{team.pk}-all_tracks"' in html
    assert 'team-track-limits' in html
    assert 'First Event' in html and 'Second Event' in html
    assert 'Alpha' in html and 'Beta' in html
    assert 'background-color: #aa0000' in html
    assert 'event-track-filter' not in html


@pytest.mark.django_db
def test_restricting_to_tracks_of_two_events_saves_and_logs(admin_client, organizer, team, tracks):
    response = _update_team(admin_client, organizer, team, limit_tracks=[t.pk for t in tracks])

    assert response.status_code == 302
    with scopes_disabled():
        assert set(team.limit_tracks.all()) == set(tracks)
        entry = LogEntry.objects.filter(action_type='eventyay.team.changed').latest('datetime')
    assert 'limit_tracks' in entry.parsed_data
    assert 'all_tracks' not in entry.parsed_data


@pytest.mark.django_db
def test_unchecking_all_tracks_without_a_track_is_rejected(admin_client, organizer, team, tracks):
    response = _update_team(admin_client, organizer, team)

    assert response.status_code == 200
    assert 'Please pick at least one track' in response.content.decode()
    with scopes_disabled():
        assert team.limit_tracks.count() == 0


@pytest.mark.django_db
def test_checking_all_tracks_removes_an_existing_restriction(admin_client, organizer, team, tracks):
    with scopes_disabled():
        team.limit_tracks.add(tracks[0])

    response = _update_team(admin_client, organizer, team, all_tracks='on', limit_tracks=[tracks[0].pk])

    assert response.status_code == 302
    with scopes_disabled():
        assert team.limit_tracks.count() == 0


@pytest.mark.django_db
def test_tracks_of_events_outside_the_team_are_dropped(admin_client, organizer, team, tracks):
    with scopes_disabled():
        first_event = tracks[0].event

    response = _update_team(
        admin_client,
        organizer,
        team,
        all_events=None,
        limit_events=[first_event.pk],
        limit_tracks=[t.pk for t in tracks],
    )

    assert response.status_code == 302
    with scopes_disabled():
        assert set(team.limit_tracks.all()) == {tracks[0]}
