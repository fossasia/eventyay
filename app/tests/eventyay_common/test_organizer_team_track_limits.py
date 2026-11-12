import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Team, Track


@pytest.fixture(autouse=True)
def _site_url(settings):
    # Without this, the control middleware redirects every request to SITE_URL.
    settings.SITE_URL = 'https://testserver'


@pytest.fixture
def tracks(event):
    with scope(event=event):
        return [
            Track.objects.create(event=event, name='Alpha', color='#111111'),
            Track.objects.create(event=event, name='Beta', color='#222222'),
        ]


@pytest.fixture
def reviewers(organizer):
    return Team.objects.create(organizer=organizer, name='Reviewers', is_reviewer=True, all_events=True)


def _update_team(client, organizer, team, **fields):
    prefix = f'team-{team.pk}'
    data = {'team_action': 'update', 'team_id': team.pk, f'{prefix}-name': team.name}
    data.update({f'{prefix}-{name}': value for name, value in fields.items()})
    return client.post(reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug}), data)


@pytest.mark.django_db
def test_teams_page_saves_tracks_from_several_events(organizer_client, organizer, tracks, reviewers):
    other_event = Event.objects.create(organizer=organizer, name='Other Event', slug='other', date_from=now())
    with scope(event=other_event):
        other_track = Track.objects.create(event=other_event, name='Gamma', color='#333333')

    response = _update_team(
        organizer_client,
        organizer,
        reviewers,
        all_events='on',
        is_reviewer='on',
        limit_tracks=[tracks[0].pk, other_track.pk],
    )

    assert response.status_code == 302
    with scopes_disabled():
        assert set(reviewers.limit_tracks.all()) == {tracks[0], other_track}


@pytest.mark.django_db
def test_teams_page_all_tracks_clears_saved_tracks(organizer_client, organizer, tracks, reviewers):
    with scopes_disabled():
        reviewers.limit_tracks.add(tracks[0])

    response = _update_team(
        organizer_client,
        organizer,
        reviewers,
        all_events='on',
        is_reviewer='on',
        all_tracks='on',
        limit_tracks=[tracks[0].pk],
    )

    assert response.status_code == 302
    with scopes_disabled():
        assert not reviewers.limit_tracks.exists()


@pytest.mark.django_db
def test_teams_page_rejects_empty_track_restriction(organizer_client, organizer, tracks, reviewers):
    response = _update_team(organizer_client, organizer, reviewers, all_events='on', is_reviewer='on')

    assert response.status_code == 200
    with scopes_disabled():
        assert not reviewers.limit_tracks.exists()
    assert 'Please select at least one track' in response.content.decode()
