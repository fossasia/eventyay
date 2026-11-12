from types import SimpleNamespace

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


def _reviewer_team_data(**extra):
    return {'name': 'Reviewers', 'all_events': True, 'is_reviewer': True, **extra}


@pytest.mark.django_db
def test_team_form_all_tracks_clears_track_limits(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
    form = TeamForm(
        _reviewer_team_data(all_tracks=True, limit_tracks=[str(track.pk)]),
        organizer=organizer,
    )
    assert form.is_valid(), form.errors
    assert list(form.cleaned_data['limit_tracks']) == []


@pytest.mark.django_db
def test_team_form_requires_a_track_when_not_all_tracks(organizer, event_with_tracks):
    form = TeamForm(_reviewer_team_data(), organizer=organizer)
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors


@pytest.mark.django_db
def test_team_form_all_tracks_initial_reflects_instance(organizer, event_with_tracks):
    with scopes_disabled():
        team = Team.objects.create(organizer=organizer, name='Reviewers', is_reviewer=True, all_events=True)
        assert TeamForm(organizer=organizer, instance=team).fields['all_tracks'].initial is True
        team.limit_tracks.add(event_with_tracks.tracks.first())
        assert TeamForm(organizer=organizer, instance=team).fields['all_tracks'].initial is False


@pytest.mark.django_db
def test_team_form_drops_tracks_of_events_outside_the_team_scope(
    organizer, event_with_tracks, event_without_tracks
):
    other_event = Event.objects.create(organizer=organizer, name='Other Event', slug='other', date_from=now())
    with scopes_disabled():
        kept = event_with_tracks.tracks.first()
        dropped = Track.objects.create(event=other_event, name='Gamma', color='333333')
    form = TeamForm(
        {
            'name': 'Reviewers',
            'is_reviewer': True,
            'limit_events': [str(event_with_tracks.pk)],
            'limit_tracks': [str(kept.pk), str(dropped.pk)],
        },
        organizer=organizer,
    )
    assert form.is_valid(), form.errors
    assert [track.pk for track in form.cleaned_data['limit_tracks']] == [kept.pk]


@pytest.mark.django_db
def test_team_form_allows_no_tracks_when_team_events_have_none(
    organizer, event_with_tracks, event_without_tracks
):
    form = TeamForm(
        {'name': 'Reviewers', 'is_reviewer': True, 'limit_events': [str(event_without_tracks.pk)]},
        organizer=organizer,
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_team_form_reports_all_tracks_toggle_as_track_change(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        # Keep "can change teams" so the form's last-admin-team safety check passes.
        team = Team.objects.create(
            organizer=organizer, name='Reviewers', is_reviewer=True, all_events=True, can_change_teams=True
        )
        team.limit_tracks.add(track)
    form = TeamForm(
        _reviewer_team_data(all_tracks=True, can_change_teams=True, limit_tracks=[str(track.pk)]),
        organizer=organizer,
        instance=team,
    )
    assert form.is_valid(), form.errors
    assert 'limit_tracks' in form.changed_data
    assert 'all_tracks' not in form.changed_data


@pytest.mark.django_db
def test_build_events_with_tracks_works_for_items_without_colour(organizer, event_without_tracks):
    # TeamShifts roles reuse this helper and have no ``color`` attribute.
    role = SimpleNamespace(pk=7, name='Stage crew', event_id=event_without_tracks.pk, event=event_without_tracks)
    groups = TeamForm._build_events_with_tracks([event_without_tracks], [role])
    assert groups[0]['tracks'] == [{'id': 7, 'name': 'Stage crew'}]
