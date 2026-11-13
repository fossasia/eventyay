import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, Track
from eventyay.control.forms.organizer_forms.team_form import TeamForm


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Track Org', slug='track-org')


@pytest.fixture
def event_with_tracks(organizer):
    event = Event.objects.create(
        organizer=organizer,
        name='Tracked Event',
        slug='tracked',
        date_from=now(),
    )
    with scopes_disabled():
        Track.objects.create(event=event, name='Alpha', color='111111')
        Track.objects.create(event=event, name='Beta', color='222222')
    return event


@pytest.fixture
def event_without_tracks(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Empty Event',
        slug='empty',
        date_from=now(),
    )


@pytest.mark.django_db
def test_team_form_lists_events_with_and_without_tracks(
    organizer, event_with_tracks, event_without_tracks
):
    form = TeamForm(organizer=organizer)
    events = {item['slug']: item for item in form.events_with_tracks}

    assert 'tracked' in events
    assert 'empty' in events
    assert len(events['tracked']['tracks']) == 2
    assert events['empty']['tracks'] == []
    assert form.has_any_tracks is True


@pytest.mark.django_db
def test_team_form_has_any_tracks_false_when_organiser_has_no_tracks(organizer):
    Event.objects.create(
        organizer=organizer,
        name='Only Event',
        slug='only',
        date_from=now(),
    )
    form = TeamForm(organizer=organizer)
    assert form.has_any_tracks is False
    assert form.events_with_tracks[0]['tracks'] == []


@pytest.mark.django_db
def test_team_form_selected_track_ids_from_instance(
    organizer, event_with_tracks
):
    with scopes_disabled():
        tracks = list(event_with_tracks.tracks.order_by('name'))
        team = Team.objects.create(
            organizer=organizer,
            name='Limited reviewers',
            is_reviewer=True,
            all_events=True,
        )
        team.limit_tracks.add(tracks[0])

    form = TeamForm(organizer=organizer, instance=team)
    assert form.selected_track_ids == {tracks[0].pk}


@pytest.mark.django_db
def test_team_form_selected_track_ids_from_post(organizer, event_with_tracks):
    with scopes_disabled():
        tracks = list(event_with_tracks.tracks.order_by('name'))

    form = TeamForm(
        {
            'name': 'Reviewers',
            'all_events': True,
            'is_reviewer': True,
            'limit_tracks': [str(tracks[0].pk), str(tracks[1].pk)],
        },
        organizer=organizer,
    )
    assert form.selected_track_ids == {tracks[0].pk, tracks[1].pk}
