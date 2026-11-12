import re

import pytest
from django.template.loader import render_to_string
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


@pytest.fixture
def second_event_with_track(organizer):
    event = Event.objects.create(
        organizer=organizer,
        name='Second Event',
        slug='second',
        date_from=now(),
    )
    with scopes_disabled():
        track = Track.objects.create(event=event, name='Gamma', color='333333')
    return track


def _post(organizer, instance=None, **overrides):
    data = {'name': 'Reviewers', 'all_events': True, 'is_reviewer': True, 'can_change_teams': True}
    data.update(overrides)
    return TeamForm(data, organizer=organizer, instance=instance)


def _save(form, organizer):
    form.instance.organizer = organizer
    return form.save()


@pytest.mark.django_db
def test_team_form_all_tracks_checked_for_new_team(organizer, event_with_tracks):
    assert TeamForm(organizer=organizer).initial['all_tracks'] is True


@pytest.mark.django_db
def test_team_form_all_tracks_reflects_saved_restriction(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        unrestricted = Team.objects.create(organizer=organizer, name='Open', is_reviewer=True, all_events=True)
        restricted = Team.objects.create(organizer=organizer, name='Limited', is_reviewer=True, all_events=True)
        restricted.limit_tracks.add(track)

    assert TeamForm(organizer=organizer, instance=unrestricted).initial['all_tracks'] is True
    assert TeamForm(organizer=organizer, instance=restricted).initial['all_tracks'] is False


@pytest.mark.django_db
def test_team_form_all_tracks_clears_ticked_tracks(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        team = Team.objects.create(organizer=organizer, name='Limited', is_reviewer=True, all_events=True)
        team.limit_tracks.add(track)

    form = _post(organizer, instance=team, all_tracks=True, limit_tracks=[str(track.pk)])
    assert form.is_valid(), form.errors
    _save(form, organizer)

    with scopes_disabled():
        assert team.limit_tracks.count() == 0


@pytest.mark.django_db
def test_team_form_saves_tracks_of_several_events_in_one_submit(organizer, event_with_tracks, second_event_with_track):
    with scopes_disabled():
        first = event_with_tracks.tracks.order_by('name').first()

    form = _post(organizer, limit_tracks=[str(first.pk), str(second_event_with_track.pk)])
    assert form.is_valid(), form.errors
    team = _save(form, organizer)

    with scopes_disabled():
        assert set(team.limit_tracks.values_list('pk', flat=True)) == {first.pk, second_event_with_track.pk}


@pytest.mark.django_db
def test_team_form_changed_data_only_lists_model_fields(organizer, event_with_tracks):
    # The team views log changed_data against model fields, so all_tracks must not show up.
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        team = Team.objects.create(organizer=organizer, name='Reviewers', is_reviewer=True, all_events=True)

    form = _post(organizer, instance=team, limit_tracks=[str(track.pk)])
    assert form.is_valid(), form.errors
    assert 'limit_tracks' in form.changed_data
    assert 'all_tracks' not in form.changed_data
    with scopes_disabled():
        for name in form.changed_data:
            Team._meta.get_field(name)


@pytest.mark.django_db
def test_team_form_ticking_all_tracks_is_reported_as_a_limit_tracks_change(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        team = Team.objects.create(organizer=organizer, name='Reviewers', is_reviewer=True, all_events=True)
        team.limit_tracks.add(track)

    # The posted track boxes are unchanged, but the stored restriction is cleared.
    form = _post(organizer, instance=team, all_tracks=True, limit_tracks=[str(track.pk)])
    assert form.is_valid(), form.errors
    assert form.has_changed()
    assert 'limit_tracks' in form.changed_data
    assert 'all_tracks' not in form.changed_data


@pytest.mark.django_db
def test_team_form_rejects_empty_restriction_when_the_teams_events_have_no_tracks(
    organizer, event_with_tracks, event_without_tracks
):
    # Saving this would store "no restriction", which also covers tracks created later.
    form = _post(organizer, all_events=False, limit_events=[str(event_without_tracks.pk)])
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors

    assert _post(organizer, all_events=False, limit_events=[str(event_without_tracks.pk)], all_tracks=True).is_valid()


@pytest.mark.django_db
def test_team_form_rejects_restriction_without_tracks(organizer, event_with_tracks):
    form = _post(organizer)
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors


@pytest.mark.django_db
def test_team_form_empty_restriction_allowed_without_talk_permissions(organizer, event_with_tracks):
    form = _post(organizer, is_reviewer=False, can_change_items=True)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_team_form_rejects_empty_restriction_when_no_tracks_exist(organizer, event_without_tracks):
    form = _post(organizer)
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors
    assert _post(organizer, all_tracks=True).is_valid()


def _render(form):
    return render_to_string('eventyay_common/organizers/teams/_permissions_fieldsets.html', {'form': form})


@pytest.mark.django_db
def test_permissions_partial_renders_grouped_checklist(organizer, event_with_tracks, second_event_with_track):
    html = _render(TeamForm(organizer=organizer))

    assert 'name="all_tracks"' in html
    assert 'team-track-limits' in html
    assert 'Tracked Event' in html and 'Second Event' in html
    assert 'Alpha' in html and 'Beta' in html and 'Gamma' in html
    assert 'event-track-filter' not in html


@pytest.mark.django_db
def test_permissions_partial_checkbox_state_follows_saved_restriction(organizer, event_with_tracks):
    with scopes_disabled():
        track = event_with_tracks.tracks.first()
        team = Team.objects.create(organizer=organizer, name='Limited', is_reviewer=True, all_events=True)
        team.limit_tracks.add(track)

    open_html = _render(TeamForm(organizer=organizer))
    restricted_html = _render(TeamForm(organizer=organizer, instance=team))

    assert re.search(r'<input[^>]*name="all_tracks"[^>]*checked', open_html)
    assert not re.search(r'<input[^>]*name="all_tracks"[^>]*checked', restricted_html)
    assert re.search(rf'<input[^>]*value="{track.pk}"[^>]*checked', restricted_html)


@pytest.mark.django_db
def test_permissions_partial_ids_are_unique_per_form_prefix(organizer, event_with_tracks):
    html = _render(TeamForm(organizer=organizer, prefix='a')) + _render(TeamForm(organizer=organizer, prefix='b'))

    assert html.count('id="track-checklist-a"') == 1
    assert html.count('id="track-checklist-b"') == 1


@pytest.mark.django_db
def test_permissions_partial_shows_the_error_even_when_there_are_no_tracks(organizer, event_without_tracks):
    form = _post(organizer)
    assert not form.is_valid()
    assert 'Please pick at least one track' in _render(form)


@pytest.mark.django_db
def test_team_form_drops_tracks_of_events_outside_the_team(organizer, event_with_tracks, second_event_with_track):
    with scopes_disabled():
        own = event_with_tracks.tracks.order_by('name').first()

    form = _post(
        organizer,
        all_events=False,
        limit_events=[str(event_with_tracks.pk)],
        limit_tracks=[str(own.pk), str(second_event_with_track.pk)],
    )
    assert form.is_valid(), form.errors
    team = _save(form, organizer)

    with scopes_disabled():
        assert list(team.limit_tracks.all()) == [own]


@pytest.mark.django_db
def test_team_form_rejects_restriction_with_only_tracks_outside_the_team(
    organizer, event_with_tracks, second_event_with_track
):
    form = _post(
        organizer,
        all_events=False,
        limit_events=[str(event_with_tracks.pk)],
        limit_tracks=[str(second_event_with_track.pk)],
    )
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors


@pytest.mark.django_db
def test_team_form_only_exposes_well_formed_track_colors(organizer, event_with_tracks):
    with scopes_disabled():
        alpha, beta = event_with_tracks.tracks.order_by('name')
        Track.objects.filter(pk=alpha.pk).update(color='#a1b2c3')
        Track.objects.filter(pk=beta.pk).update(color='red;}')

    tracks = TeamForm(organizer=organizer).events_with_tracks[0]['tracks']
    assert {t['name']: t['color'] for t in tracks} == {'Alpha': '#a1b2c3', 'Beta': ''}


@pytest.mark.django_db
def test_team_form_rejects_tracks_of_another_organizer(organizer, event_with_tracks):
    other = Organizer.objects.create(name='Other Org', slug='other-org')
    other_event = Event.objects.create(organizer=other, name='Foreign', slug='foreign', date_from=now())
    with scopes_disabled():
        foreign = Track.objects.create(event=other_event, name='Foreign track', color='444444')

    form = _post(organizer, limit_tracks=[str(foreign.pk)])
    assert not form.is_valid()
    assert 'limit_tracks' in form.errors
