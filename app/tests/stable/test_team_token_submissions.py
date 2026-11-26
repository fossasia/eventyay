"""Team API tokens: listing, retrieving and creating submissions through the API."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django_scopes import scope, scopes_disabled
from rest_framework.test import APIRequestFactory

from eventyay.api.views.submission import SubmissionViewSet
from eventyay.base.models import Organizer, SpeakerProfile, Submission, TeamAPIToken, Track
from eventyay.talk_rules.tracks import apply_team_track_limit


User = get_user_model()


def _team_token(event, can_change_submissions, name, limit_tracks=(), **team_fields):
    with scope(event=event):
        team = event.organizer.teams.create(name=name, can_change_submissions=can_change_submissions, **team_fields)
        team.limit_events.add(event)
        if limit_tracks:
            team.limit_tracks.set(limit_tracks)
        return TeamAPIToken.objects.create(team=team, name=name)


def _headers(token):
    return {'Authorization': f'Token {token.token}'}


def _make_submission(event, title, speaker=None, track=None):
    with scope(event=event):
        submission = Submission.objects.create(
            title=title, event=event, submission_type=event.cfp.default_type, track=track
        )
        if speaker is not None:
            submission.speakers.add(speaker)
        return submission


@pytest.fixture
def speaker(event):
    with scopes_disabled():
        user = User.objects.create_user(email='speaker@example.com', password='speakerpwd1!', fullname='Jane Speaker')
    with scope(event=event):
        SpeakerProfile.objects.create(user=user, event=event, biography='Best speaker in the world.')
    return user


@pytest.fixture
def tracks(event):
    with scope(event=event):
        event.feature_flags['use_tracks'] = True
        event.save()
        return (
            Track.objects.create(name='Track one', color='00ff00', event=event),
            Track.objects.create(name='Track two', color='ff0000', event=event),
        )


@pytest.fixture
def submission(event, speaker):
    return _make_submission(event, 'An unscheduled talk', speaker=speaker)


@pytest.mark.django_db
def test_team_token_can_list_and_retrieve_unscheduled_submissions(client, event, submission):
    token = _team_token(event, True, 'Manage submissions')

    response = client.get(event.api_urls.submissions, follow=True, headers=_headers(token))
    assert response.status_code == 200, response.text
    assert [s['code'] for s in response.json()['results']] == [submission.code]

    response = client.get(event.api_urls.submissions + f'{submission.code}/', follow=True, headers=_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()['code'] == submission.code


@pytest.mark.django_db
def test_team_token_without_submission_permission_cannot_see_unscheduled_submissions(client, event, submission):
    token = _team_token(event, False, 'No submission rights')

    response = client.get(event.api_urls.submissions, follow=True, headers=_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()['count'] == 0

    response = client.get(event.api_urls.submissions + f'{submission.code}/', follow=True, headers=_headers(token))
    assert response.status_code == 404


@pytest.mark.django_db
def test_team_token_respects_track_limits(client, event, speaker, tracks):
    track, other_track = tracks
    allowed = _make_submission(event, 'In the allowed track', speaker=speaker, track=track)
    hidden = _make_submission(event, 'In another track', speaker=speaker, track=other_track)
    token = _team_token(event, True, 'Track limited', limit_tracks=[track])

    response = client.get(event.api_urls.submissions, follow=True, headers=_headers(token))
    assert response.status_code == 200, response.text
    assert [s['code'] for s in response.json()['results']] == [allowed.code]

    response = client.get(event.api_urls.submissions + f'{hidden.code}/', follow=True, headers=_headers(token))
    assert response.status_code == 404


@pytest.mark.django_db
def test_team_token_honours_force_hide_speaker_names(client, event, submission):
    visible = _team_token(event, True, 'Shows speakers')
    hidden = _team_token(event, True, 'Hides speakers', force_hide_speaker_names=True)
    url = event.api_urls.submissions + f'{submission.code}/?expand=speakers'

    response = client.get(url, follow=True, headers=_headers(visible))
    assert response.status_code == 200, response.text
    assert response.json()['speakers']

    response = client.get(url, follow=True, headers=_headers(hidden))
    assert response.status_code == 200, response.text
    assert response.json()['speakers'] == []


@pytest.mark.django_db
def test_team_token_of_other_event_cannot_see_unscheduled_submissions(client, event, submission):
    with scopes_disabled():
        other_organizer = Organizer.objects.create(name='Other Organizer', slug='otherorg')
        other_event = type(event).objects.create(
            organizer=other_organizer,
            name='Other Event',
            slug='otherevent',
            date_from=event.date_from,
            date_to=event.date_to,
            currency='USD',
            locale='en',
            is_public=True,
            live=True,
        )
    token = _team_token(other_event, True, 'Other event')

    response = client.get(event.api_urls.submissions, follow=True, headers=_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()['count'] == 0


@pytest.mark.django_db
def test_team_token_can_create_submission(client, event, allow_all_entitlements):
    token = _team_token(event, True, 'SubToken')

    response = client.post(
        event.api_urls.submissions,
        follow=True,
        data={
            'title': 'Team Token Submission',
            'submission_type': event.cfp.default_type.pk,
            'abstract': 'Abstract',
            'description': 'Description',
            'duration': 45,
            'content_locale': 'en',
        },
        content_type='application/json',
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    content = response.json()
    assert content['duration'] == 45
    assert content['title'] == 'Team Token Submission'


@pytest.mark.django_db
def test_team_token_read_only_team_forbidden_submission(client, event):
    token = _team_token(event, False, 'ReadToken')

    response = client.post(
        event.api_urls.submissions,
        follow=True,
        data={'title': 'Team Token Submission', 'submission_type': event.cfp.default_type.pk},
        content_type='application/json',
        headers=_headers(token),
    )
    assert response.status_code in [403, 401]


@pytest.mark.django_db
def test_apply_team_track_limit_works_without_an_active_scope(event, speaker, tracks):
    track, other_track = tracks
    allowed = _make_submission(event, 'In the allowed track', speaker=speaker, track=track)
    other = _make_submission(event, 'In another track', speaker=speaker, track=other_track)
    unlimited = _team_token(event, True, 'Unlimited').team
    limited = _team_token(event, True, 'Limited', limit_tracks=[track]).team
    with scope(event=event):
        queryset = event.submissions.all()

    # Called outside any scope, as the API view can do for a team token.
    assert {s.code for s in apply_team_track_limit(queryset, event, unlimited)} == {allowed.code, other.code}
    assert {s.code for s in apply_team_track_limit(queryset, event, limited)} == {allowed.code}


def _team_token_view(event, token):
    request = APIRequestFactory().get(event.api_urls.submissions)
    request.user = AnonymousUser()
    request.auth = token
    request.eventpermset = {'can_change_submissions'}
    view = SubmissionViewSet()
    view.event = event
    view.request = request
    return view


@pytest.mark.django_db
def test_team_token_speaker_profiles_come_from_visible_submissions(event, speaker, tracks):
    track, other_track = tracks
    with scopes_disabled():
        other_speaker = User.objects.create_user(
            email='other@example.com', password='speakerpwd1!', fullname='John Speaker'
        )
    with scope(event=event):
        SpeakerProfile.objects.create(user=other_speaker, event=event, biography='Another speaker.')
    _make_submission(event, 'In the allowed track', speaker=speaker, track=track)
    _make_submission(event, 'In another track', speaker=other_speaker, track=other_track)

    unlimited = _team_token_view(event, _team_token(event, True, 'Unlimited'))
    limited = _team_token_view(event, _team_token(event, True, 'Limited', limit_tracks=[track]))

    with scope(event=event):
        assert {p.user_id for p in unlimited.speaker_profiles_for_user} == {speaker.pk, other_speaker.pk}
        assert {p.user_id for p in limited.speaker_profiles_for_user} == {speaker.pk}
