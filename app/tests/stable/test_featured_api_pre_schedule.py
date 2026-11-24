import json

import pytest
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    Room,
    SpeakerProfile,
    Submission,
    SubmissionStates,
    SubmissionType,
    TalkSlot,
)


User = get_user_model()


@pytest.fixture
def pre_schedule_event(event):
    with scope(event=event):
        event.is_public = True
        event.talks_published = False
        event.feature_flags['show_schedule'] = False
        event.feature_flags['show_featured'] = 'until_schedule'
        event.feature_flags['show_featured_speakers'] = 'until_schedule'
        event.save()
    return event


@pytest.fixture
def featured_setup(pre_schedule_event):
    event = pre_schedule_event
    with scope(event=event):
        stype = SubmissionType.objects.create(event=event, name='Talk', default_duration=30)

        # Speaker 1: Featured, position 2, confirmed featured talk
        user1 = User.objects.create_user(
            email='alice@example.com',
            password='testpass123',
            fullname='Alice Speaker',
        )
        profile1 = SpeakerProfile.objects.create(
            event=event,
            user=user1,
            biography='Alice biography.',
            is_featured=True,
            position=2,
        )
        sub1 = Submission.objects.create(
            event=event,
            submission_type=stype,
            title='Featured Confirmed Talk 1',
            state=SubmissionStates.CONFIRMED,
            is_featured=True,
        )
        sub1.speakers.add(user1)

        # Speaker 2: Featured, position 1, confirmed featured talk
        user2 = User.objects.create_user(
            email='bob@example.com',
            password='testpass123',
            fullname='Bob Keynote',
        )
        profile2 = SpeakerProfile.objects.create(
            event=event,
            user=user2,
            biography='Bob biography.',
            is_featured=True,
            position=1,
        )
        sub2 = Submission.objects.create(
            event=event,
            submission_type=stype,
            title='Featured Confirmed Talk 2',
            state=SubmissionStates.ACCEPTED,
            is_featured=True,
        )
        sub2.speakers.add(user2)

        # Speaker 3: Not featured, confirmed talk NOT featured
        user3 = User.objects.create_user(
            email='charlie@example.com',
            password='testpass123',
            fullname='Charlie Regular',
        )
        profile3 = SpeakerProfile.objects.create(
            event=event,
            user=user3,
            biography='Charlie biography.',
            is_featured=False,
            position=None,
        )
        sub3 = Submission.objects.create(
            event=event,
            submission_type=stype,
            title='Regular Confirmed Talk',
            state=SubmissionStates.CONFIRMED,
            is_featured=False,
        )
        sub3.speakers.add(user3)

        # Speaker 4: In-review proposal (SUBMITTED), marked featured on profile & proposal
        user4 = User.objects.create_user(
            email='dave@example.com',
            password='testpass123',
            fullname='Dave Applicant',
        )
        profile4 = SpeakerProfile.objects.create(
            event=event,
            user=user4,
            biography='Dave biography.',
            is_featured=True,
            position=3,
        )
        sub4 = Submission.objects.create(
            event=event,
            submission_type=stype,
            title='Submitted In-Review Talk',
            state=SubmissionStates.SUBMITTED,
            is_featured=True,
        )
        sub4.speakers.add(user4)

    return {
        'event': event,
        'user1': user1,
        'profile1': profile1,
        'sub1': sub1,
        'user2': user2,
        'profile2': profile2,
        'sub2': sub2,
        'user3': user3,
        'profile3': profile3,
        'sub3': sub3,
        'user4': user4,
        'profile4': profile4,
        'sub4': sub4,
    }


@pytest.mark.django_db
def test_featured_submissions_and_speakers_pre_schedule(client, featured_setup):
    """Anonymous client can list featured sessions and featured speakers pre-schedule."""
    event = featured_setup['event']
    sub1 = featured_setup['sub1']
    sub2 = featured_setup['sub2']
    sub3 = featured_setup['sub3']
    sub4 = featured_setup['sub4']
    user1 = featured_setup['user1']
    user2 = featured_setup['user2']
    user3 = featured_setup['user3']
    user4 = featured_setup['user4']

    # 1. GET /api/v1/events/{event}/submissions/
    resp = client.get(event.api_urls.submissions, follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert content['count'] == 2
    returned_codes = {item['code'] for item in content['results']}
    assert returned_codes == {sub1.code, sub2.code}
    assert sub3.code not in returned_codes
    assert sub4.code not in returned_codes

    for item in content['results']:
        assert item['is_featured'] is True
        # Verify private/internal notes are omitted
        assert 'notes' not in item
        assert 'internal_notes' not in item
        assert 'invitation_token' not in item

    # 2. GET /api/v1/events/{event}/speakers/
    resp_spk = client.get(event.api_urls.speakers, follow=True)
    assert resp_spk.status_code == 200
    content_spk = json.loads(resp_spk.text)
    assert content_spk['count'] == 2
    spk_results = content_spk['results']
    # Bob (position=1) should be first, Alice (position=2) second
    assert spk_results[0]['code'] == user2.code
    assert spk_results[0]['fullname'] == user2.fullname
    assert spk_results[0]['is_featured'] is True
    assert spk_results[0]['featured_position'] == 1

    assert spk_results[1]['code'] == user1.code
    assert spk_results[1]['fullname'] == user1.fullname
    assert spk_results[1]['is_featured'] is True
    assert spk_results[1]['featured_position'] == 2

    # Non-featured Charlie and unaccepted Dave should not appear
    spk_codes = {s['code'] for s in spk_results}
    assert user3.code not in spk_codes
    assert user4.code not in spk_codes

    # Email must not leak for public users
    for s in spk_results:
        assert 'email' not in s


@pytest.mark.django_db
def test_featured_detail_endpoints_pre_schedule(client, featured_setup):
    """Retrieve endpoints allow public access to featured items, 404 for unfeatured/unaccepted."""
    event = featured_setup['event']
    sub1 = featured_setup['sub1']
    sub3 = featured_setup['sub3']
    sub4 = featured_setup['sub4']
    user1 = featured_setup['user1']
    user3 = featured_setup['user3']
    user4 = featured_setup['user4']

    # Submissions detail
    resp1 = client.get(f'{event.api_urls.submissions}{sub1.code}/', follow=True)
    assert resp1.status_code == 200
    assert json.loads(resp1.text)['code'] == sub1.code
    assert json.loads(resp1.text)['is_featured'] is True

    # Unfeatured confirmed session -> 404
    resp3 = client.get(f'{event.api_urls.submissions}{sub3.code}/', follow=True)
    assert resp3.status_code == 404

    # Unaccepted submitted session -> 404
    resp4 = client.get(f'{event.api_urls.submissions}{sub4.code}/', follow=True)
    assert resp4.status_code == 404

    # Speakers detail
    resp_spk1 = client.get(f'{event.api_urls.speakers}{user1.code}/', follow=True)
    assert resp_spk1.status_code == 200
    assert json.loads(resp_spk1.text)['code'] == user1.code
    assert json.loads(resp_spk1.text)['is_featured'] is True

    # Unfeatured speaker -> 404
    resp_spk3 = client.get(f'{event.api_urls.speakers}{user3.code}/', follow=True)
    assert resp_spk3.status_code == 404

    # Unaccepted speaker -> 404
    resp_spk4 = client.get(f'{event.api_urls.speakers}{user4.code}/', follow=True)
    assert resp_spk4.status_code == 404


@pytest.mark.django_db
def test_featured_disabled_returns_empty_or_forbidden(client, featured_setup):
    """When show_featured/show_featured_speakers are 'never', results are hidden."""
    event = featured_setup['event']
    with scope(event=event):
        event.feature_flags['show_featured'] = 'never'
        event.feature_flags['show_featured_speakers'] = 'never'
        event.save()

    # Submissions returns empty list
    resp = client.get(event.api_urls.submissions, follow=True)
    assert resp.status_code == 200
    assert json.loads(resp.text)['count'] == 0

    # Speakers endpoint is not publicly permitted when schedule is not released
    resp_spk = client.get(event.api_urls.speakers, follow=True)
    assert resp_spk.status_code in (200, 401)
    if resp_spk.status_code == 200:
        assert json.loads(resp_spk.text)['count'] == 0


@pytest.mark.django_db
def test_schedule_release_reveals_all_sessions_without_duplicates(client, featured_setup):
    """Once a schedule is released, all scheduled talks and speakers appear correctly."""
    event = featured_setup['event']
    sub1 = featured_setup['sub1']
    sub2 = featured_setup['sub2']
    sub3 = featured_setup['sub3']

    with scope(event=event):
        room = Room.objects.create(event=event, name='Main Hall', position=1)
        for s in (sub1, sub2, sub3):
            s.state = SubmissionStates.CONFIRMED
            s.save()
            TalkSlot.objects.update_or_create(
                submission=s,
                schedule=event.wip_schedule,
                defaults={'is_visible': True, 'room': room, 'start': now()},
            )
        event.feature_flags['show_featured'] = 'always'
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.talks_published = True
        event.save()
        # Release schedule
        event.release_schedule('v1')

    # Submissions
    resp = client.get(event.api_urls.submissions, follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    codes = [item['code'] for item in content['results']]
    # No duplicates
    assert len(codes) == len(set(codes))
    # All confirmed scheduled talks included
    assert sub1.code in codes
    assert sub2.code in codes
    assert sub3.code in codes

    # Speakers
    resp_spk = client.get(event.api_urls.speakers, follow=True)
    assert resp_spk.status_code == 200
    spk_content = json.loads(resp_spk.text)
    spk_codes = [s['code'] for s in spk_content['results']]
    assert len(spk_codes) == len(set(spk_codes))
    # Featured speakers appear first
    assert spk_content['results'][0]['is_featured'] is True


@pytest.mark.django_db
def test_legacy_featured_api_pre_schedule(client, featured_setup):
    """Legacy API version returns featured sessions and speakers pre-schedule."""
    from eventyay.api.versions import LEGACY

    event = featured_setup['event']
    sub1 = featured_setup['sub1']
    sub2 = featured_setup['sub2']
    sub3 = featured_setup['sub3']
    user1 = featured_setup['user1']
    user2 = featured_setup['user2']
    user3 = featured_setup['user3']

    # Submissions
    resp = client.get(
        event.api_urls.submissions,
        headers={'Pretalx-Version': LEGACY},
        follow=True,
    )
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert content['count'] == 2
    codes = {item['code'] for item in content['results']}
    assert codes == {sub1.code, sub2.code}
    assert sub3.code not in codes
    for item in content['results']:
        assert item['is_featured'] is True

    # Speakers
    resp_spk = client.get(
        event.api_urls.speakers,
        headers={'Pretalx-Version': LEGACY},
        follow=True,
    )
    assert resp_spk.status_code == 200
    spk_content = json.loads(resp_spk.text)
    assert spk_content['count'] == 2
    spk_codes = {s['code'] for s in spk_content['results']}
    assert spk_codes == {user1.code, user2.code}
    assert user3.code not in spk_codes
    for s in spk_content['results']:
        assert s['is_featured'] is True
