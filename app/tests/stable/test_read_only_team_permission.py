"""A team with only "Read-only access to event information" gives integrations read access and nothing else."""

import datetime as dt
import json

import pytest
from django.test import override_settings
from django_scopes import scope

from eventyay.base.models import (
    Review,
    ReviewPhase,
    Room,
    SpeakerProfile,
    Submission,
    SubmissionType,
    Tag,
    TalkSlot,
    Team,
    Track,
    User,
)
from eventyay.base.models.auth_token import ENDPOINTS, WRITE_PERMISSIONS, UserApiToken
from eventyay.control.forms.organizer_forms.team_form import TeamForm


pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('allow_all_entitlements')]


@pytest.fixture
def read_only_team(organizer, event):
    team = Team.objects.create(organizer=organizer, name='Website', can_view_event_info=True)
    team.limit_events.add(event)
    return team


@pytest.fixture
def read_only_client(client, read_only_team):
    token = read_only_team.tokens.create(name='Website')
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.token}'
    return client


@pytest.fixture
def settings_team_client(client, organizer, event):
    team = Team.objects.create(organizer=organizer, name='Settings', can_change_event_settings=True)
    team.limit_events.add(event)
    token = team.tokens.create(name='Settings')
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.token}'
    return client


@pytest.fixture
def program(event):
    """A published schedule with one confirmed session and one session that is not public yet."""
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        track = Track.objects.create(event=event, name='Main', color='#000000')
        room = Room.objects.create(event=event, name='Room A')
        speaker = User.objects.create_user(email='speaker@example.com', password='speakerpass123', fullname='Ada')
        hidden_speaker = User.objects.create_user(email='hidden@example.com', password='hiddenpass123', fullname='Bo')
        SpeakerProfile.objects.create(user=speaker, event=event, biography='Public bio')
        SpeakerProfile.objects.create(user=hidden_speaker, event=event, biography='Hidden bio')

        public = Submission.objects.create(
            title='Public session', event=event, submission_type=submission_type, track=track, content_locale='en'
        )
        public.speakers.add(speaker)
        public.accept()
        public.confirm()

        private = Submission.objects.create(
            title='Private proposal', event=event, submission_type=submission_type, content_locale='en'
        )
        private.speakers.add(hidden_speaker)

        start = event.date_from + dt.timedelta(hours=10)
        TalkSlot.objects.update_or_create(
            submission=public,
            schedule=event.wip_schedule,
            defaults={'is_visible': True, 'start': start, 'end': start + dt.timedelta(hours=1), 'room': room},
        )
        event.release_schedule('v1')
    event.talks_published = True
    event.save(update_fields=['talks_published'])
    return {'public': public, 'private': private, 'track': track}


def event_url(event, path=''):
    return f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/{path}'


def test_team_with_only_read_only_permission_can_be_saved(organizer, event):
    form = TeamForm(
        organizer=organizer,
        data={'name': 'Website', 'limit_events': [event.pk], 'can_view_event_info': 'on', 'all_tracks': 'on'},
    )
    assert form.is_valid(), form.errors
    form.instance.organizer = organizer
    team = form.save()
    assert team.permission_set() == {'can_view_event_info'}


def test_team_without_permissions_is_still_rejected(organizer, event):
    form = TeamForm(organizer=organizer, data={'name': 'Empty', 'limit_events': [event.pk], 'all_tracks': 'on'})
    assert not form.is_valid()


def test_existing_teams_do_not_gain_the_permission(organizer):
    team = Team.objects.create(organizer=organizer, name='Old', can_change_event_settings=True)
    assert 'can_view_event_info' not in team.permission_set()


def test_read_only_token_reads_event(read_only_client, event):
    response = read_only_client.get(f'/api/v1/organizers/{event.organizer.slug}/events/')
    assert response.status_code == 200
    assert [result['slug'] for result in response.json()['results']] == [event.slug]

    response = read_only_client.get(event_url(event))
    assert response.status_code == 200
    assert response.json()['slug'] == event.slug


def test_read_only_token_reads_only_public_settings(read_only_client, event):
    event.settings.frontpage_text = 'Welcome'
    event.settings.primary_color = '#123456'
    event.settings.mail_from = 'orga@example.com'

    response = read_only_client.get(event_url(event, 'settings/'))
    assert response.status_code == 200
    data = response.json()
    assert data['frontpage_text'] == {'en': 'Welcome'}
    assert data['primary_color'] == '#123456'
    for private_setting in ('mail_from', 'invoice_numbers_prefix', 'payment_term_days', 'cancel_allow_user'):
        assert private_setting not in data

    response = read_only_client.get(event_url(event, 'settings/') + '?explain=true')
    assert response.status_code == 200
    assert 'mail_from' not in response.json()


def test_settings_team_still_reads_all_settings(settings_team_client, event):
    response = settings_team_client.get(event_url(event, 'settings/'))
    assert response.status_code == 200
    assert 'mail_from' in response.json()


def test_read_only_token_cannot_change_event(read_only_client, event):
    event.settings.frontpage_text = 'Welcome'

    response = read_only_client.patch(
        event_url(event, 'settings/'), data=json.dumps({'frontpage_text': 'Hacked'}), content_type='application/json'
    )
    assert response.status_code == 403
    assert 'permission' in response.json()['detail'].lower()
    event.settings.flush()
    assert str(event.settings.frontpage_text) == 'Welcome'

    response = read_only_client.patch(
        event_url(event), data=json.dumps({'name': {'en': 'Hacked'}}), content_type='application/json'
    )
    assert response.status_code == 403

    response = read_only_client.delete(event_url(event))
    assert response.status_code == 403

    response = read_only_client.post(
        event_url(event, 'products/'),
        data=json.dumps({'name': {'en': 'Free beer'}, 'default_price': '0.00'}),
        content_type='application/json',
    )
    assert response.status_code == 403

    response = read_only_client.post(event_url(event, 'publish_talks/'))
    assert response.status_code in (403, 404, 405)

    event.refresh_from_db()
    assert str(event.name) == 'Test Event'


def test_read_only_token_reads_ticket_types(read_only_client, event):
    for path in ('products/', 'categories/', 'quotas/', 'questions/', 'taxrules/', 'subevents/'):
        response = read_only_client.get(event_url(event, path))
        assert response.status_code == 200, path


@pytest.mark.parametrize(
    'path',
    [
        'orders/',
        'orderpositions/',
        'invoices/',
        'vouchers/',
        'waitinglistentries/',
        'checkinlists/',
        'revokedsecrets/',
        'cartpositions/',
    ],
)
def test_read_only_token_has_no_private_ticket_data(read_only_client, event, path):
    response = read_only_client.get(event_url(event, path))
    assert response.status_code == 403


@pytest.mark.parametrize('path', ['giftcards/', 'teams/', 'webhooks/', 'devices/'])
def test_read_only_token_has_no_organizer_data(read_only_client, organizer, path):
    response = read_only_client.get(f'/api/v1/organizers/{organizer.slug}/{path}')
    assert response.status_code == 403


@override_settings(SITE_URL='http://testserver')
def test_read_only_token_reads_published_program(read_only_client, event, program):
    response = read_only_client.get(
        event_url(event, 'submissions/') + '?expand=speakers,track,submission_type,slots.room&state=confirmed'
    )
    assert response.status_code == 200
    results = response.json()['results']
    assert [result['code'] for result in results] == [program['public'].code]

    response = read_only_client.get(event_url(event, 'submissions/'))
    codes = {result['code'] for result in response.json()['results']}
    assert program['private'].code not in codes

    response = read_only_client.get(event_url(event, 'speakers/'))
    assert response.status_code == 200
    speakers = response.json()['results']
    assert [speaker['fullname'] for speaker in speakers] == ['Ada']
    assert 'email' not in speakers[0]

    for path in ('slots/', 'rooms/', 'tracks/', 'schedules/'):
        response = read_only_client.get(event_url(event, path))
        assert response.status_code == 200, path


@pytest.fixture
def submissions_team_client(client, organizer, event):
    team = Team.objects.create(organizer=organizer, name='Program', can_change_submissions=True)
    team.limit_events.add(event)
    token = team.tokens.create(name='Program')
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.token}'
    return client


@override_settings(SITE_URL='http://testserver')
def test_read_only_token_cannot_change_program(read_only_client, event, program):
    public = program['public']
    with scope(event=event):
        slot = event.current_schedule.talks.get(submission=public)
        room = slot.room
        speaker_code = public.speakers.first().code

    writes = [
        ('patch', f'submissions/{public.code}/', {'title': 'Hacked'}),
        ('delete', f'submissions/{public.code}/', None),
        ('post', 'submissions/', {'title': 'Injected'}),
        ('patch', f'speakers/{speaker_code}/', {'biography': 'Hacked'}),
        ('patch', f'slots/{slot.pk}/', {'description': 'Hacked'}),
        ('post', 'schedules/release/', {'version': 'hacked'}),
        ('patch', f'rooms/{room.pk}/', {'name': 'Hacked'}),
        ('patch', f'tracks/{program["track"].pk}/', {'name': 'Hacked'}),
        ('post', 'tracks/', {'name': 'New', 'color': '#000000'}),
        ('post', 'tags/', {'tag': 'New', 'color': '#000000'}),
        ('post', 'submission-types/', {'name': 'New', 'default_duration': 30}),
        ('post', 'reviews/', {'submission': public.code, 'text': 'Hacked'}),
    ]
    for method, path, data in writes:
        kwargs = {'data': json.dumps(data), 'content_type': 'application/json'} if data is not None else {}
        response = getattr(read_only_client, method)(event_url(event, path), **kwargs)
        assert response.status_code == 403, (method, path, response.status_code)

    with scope(event=event):
        public.refresh_from_db()
        program['track'].refresh_from_db()
        room.refresh_from_db()
        assert event.schedules.filter(version='hacked').count() == 0
        assert not Submission.objects.filter(event=event, title='Injected').exists()
    assert public.title == 'Public session'
    assert str(program['track'].name) == 'Main'
    assert str(room.name) == 'Room A'


@pytest.mark.parametrize('path', ['mail-templates/', 'access-codes/', 'speaker-information/'])
def test_read_only_token_has_no_private_talk_data(read_only_client, event, path):
    response = read_only_client.get(event_url(event, path))
    assert response.status_code == 403


@override_settings(SITE_URL='http://testserver')
def test_read_only_token_has_no_reviews_or_unpublished_answers(read_only_client, event, program):
    for path in ('reviews/', 'answers/'):
        response = read_only_client.get(event_url(event, path))
        assert response.status_code == 403 or response.json()['count'] == 0, path


@override_settings(SITE_URL='http://testserver')
def test_submissions_team_can_still_change_sessions(submissions_team_client, event, program):
    public = program['public']
    response = submissions_team_client.patch(
        event_url(event, f'submissions/{public.code}/'),
        data=json.dumps({'title': 'Renamed'}),
        content_type='application/json',
    )
    assert response.status_code == 200, response.content
    with scope(event=event):
        public.refresh_from_db()
    assert public.title == 'Renamed'

    response = submissions_team_client.get(event_url(event, 'mail-templates/'))
    assert response.status_code == 200


@pytest.fixture
def review_phase(event):
    with scope(event=event):
        event.review_phases.all().delete()
        return ReviewPhase.objects.create(
            event=event,
            name='Review',
            is_active=True,
            can_review=True,
            can_see_other_reviews='always',
            can_change_submission_state=False,
            can_tag_submissions='none',
        )


@pytest.fixture
def reviewers(organizer, event):
    team = Team.objects.create(organizer=organizer, name='Reviewers', is_reviewer=True)
    team.limit_events.add(event)
    users = []
    for name in ('alice', 'bob'):
        user = User.objects.create_user(email=f'{name}@example.com', password=f'{name}pass12345', fullname=name)
        team.members.add(user)
        users.append(user)
    return users


@pytest.fixture
def proposal(event):
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        speaker = User.objects.create_user(email='author@example.com', password='authorpass123', fullname='Author')
        SpeakerProfile.objects.create(user=speaker, event=event)
        submission = Submission.objects.create(
            title='Proposal', event=event, submission_type=submission_type, content_locale='en'
        )
        submission.speakers.add(speaker)
        return submission


def user_client(client, user, event):
    token = UserApiToken.objects.create(name='Reviewer', user=user)
    token.events.set([event])
    token.endpoints = {endpoint: list(WRITE_PERMISSIONS) for endpoint in ENDPOINTS}
    token.save()
    client.defaults['HTTP_AUTHORIZATION'] = f'Token {token.token}'
    return client


@override_settings(SITE_URL='http://testserver')
def test_reviewer_cannot_change_another_reviewers_review(client, event, reviewers, proposal, review_phase):
    alice, bob = reviewers
    with scope(event=event):
        bobs_review = Review.objects.create(submission=proposal, user=bob, text='Good')
        alices_review = Review.objects.create(submission=proposal, user=alice, text='Fine')
    client = user_client(client, alice, event)

    response = client.patch(
        event_url(event, f'reviews/{bobs_review.pk}/'),
        data=json.dumps({'text': 'Bad'}),
        content_type='application/json',
    )
    assert response.status_code == 403
    response = client.delete(event_url(event, f'reviews/{bobs_review.pk}/'))
    assert response.status_code == 403

    response = client.patch(
        event_url(event, f'reviews/{alices_review.pk}/'),
        data=json.dumps({'text': 'Better'}),
        content_type='application/json',
    )
    assert response.status_code == 200, response.content

    with scope(event=event):
        bobs_review.refresh_from_db()
        alices_review.refresh_from_db()
    assert bobs_review.text == 'Good'
    assert alices_review.text == 'Better'


@override_settings(SITE_URL='http://testserver')
def test_reviewer_cannot_change_own_review_when_reviews_are_closed(client, event, reviewers, proposal, review_phase):
    alice = reviewers[0]
    with scope(event=event):
        review = Review.objects.create(submission=proposal, user=alice, text='Fine')
    review_phase.can_review = False
    review_phase.save()
    client = user_client(client, alice, event)

    response = client.delete(event_url(event, f'reviews/{review.pk}/'))
    assert response.status_code == 403
    with scope(event=event):
        assert Review.objects.filter(pk=review.pk).exists()


@override_settings(SITE_URL='http://testserver')
@pytest.mark.parametrize('allowed', [True, False])
def test_reviewer_state_changes_follow_review_phase(client, event, reviewers, proposal, review_phase, allowed):
    review_phase.can_change_submission_state = allowed
    review_phase.save()
    client = user_client(client, reviewers[0], event)

    response = client.post(event_url(event, f'submissions/{proposal.code}/accept/'))
    assert response.status_code == (200 if allowed else 403), response.content
    response = client.patch(
        event_url(event, f'submissions/{proposal.code}/'),
        data=json.dumps({'title': 'Changed'}),
        content_type='application/json',
    )
    assert response.status_code == 403

    with scope(event=event):
        proposal.refresh_from_db()
    assert proposal.state == ('accepted' if allowed else 'submitted')
    assert proposal.title == 'Proposal'


@override_settings(SITE_URL='http://testserver')
@pytest.mark.parametrize(('tag_phase', 'can_create', 'can_change'), [
    ('none', False, False),
    ('use_tags', False, True),
    ('create_tags', True, False),
])
def test_reviewer_tag_changes_follow_review_phase(
    client, event, reviewers, review_phase, tag_phase, can_create, can_change
):
    review_phase.can_tag_submissions = tag_phase
    review_phase.save()
    with scope(event=event):
        tag = Tag.objects.create(event=event, tag='Existing', color='#000000')
    client = user_client(client, reviewers[0], event)

    response = client.post(
        event_url(event, 'tags/'), data=json.dumps({'tag': 'New', 'color': '#000000'}), content_type='application/json'
    )
    assert response.status_code == (201 if can_create else 403), response.content
    response = client.delete(event_url(event, f'tags/{tag.pk}/'))
    assert response.status_code == (204 if can_change else 403), response.content


@override_settings(SITE_URL='http://testserver')
def test_reviewer_can_only_review_reviewable_proposals(client, event, reviewers, proposal, review_phase):
    with scope(event=event):
        accepted = Submission.objects.create(
            title='Accepted', event=event, submission_type=proposal.submission_type, content_locale='en'
        )
        accepted.speakers.add(proposal.speakers.first())
        accepted.accept()
    client = user_client(client, reviewers[0], event)

    response = client.post(
        event_url(event, 'reviews/'),
        data=json.dumps({'submission': accepted.code, 'text': 'Late'}),
        content_type='application/json',
    )
    assert response.status_code == 400

    response = client.post(
        event_url(event, 'reviews/'),
        data=json.dumps({'submission': proposal.code, 'text': 'Good'}),
        content_type='application/json',
    )
    assert response.status_code == 201, response.content
    review_id = response.json()['id']

    response = client.patch(
        event_url(event, f'reviews/{review_id}/'),
        data=json.dumps({'submission': accepted.code}),
        content_type='application/json',
    )
    assert response.status_code == 400
    response = client.patch(
        event_url(event, f'reviews/{review_id}/'),
        data=json.dumps({'submission': proposal.code, 'text': 'Very good'}),
        content_type='application/json',
    )
    assert response.status_code == 200, response.content

    with scope(event=event):
        review = Review.objects.get(pk=review_id)
        assert review.submission == proposal
        assert review.text == 'Very good'
        assert not accepted.reviews.exists()
