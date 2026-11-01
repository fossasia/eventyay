from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Submission, SubmissionStates, SubmissionType, User
from eventyay.base.models.submission import SpeakerRole


@pytest.fixture
def test_user():
    """Create a regular test user."""
    return User.objects.create_user('stats@example.com', 'password')

@pytest.fixture
def staff_user():
    """Create a staff user."""
    user = User.objects.create_user('staff@example.com', 'password')
    user.is_staff = True
    user.is_active = True
    user.save()
    return user

@pytest.fixture
def admin_client(db, staff_client, staff_user):
    """Staff client with an active sudo/staff session for admin views."""
    from eventyay.base.models.auth import StaffSession

    session = staff_client.session
    session.save()
    StaffSession.objects.create(
        user=staff_user,
        session_key=session.session_key,
        comment='test',
    )
    return staff_client

@pytest.fixture
def orga(test_user):
    """Create a test organizer and admin team."""
    organizer = Organizer.objects.create(name='Stats Orga', slug='stats-orga')
    team = organizer.teams.create(
        name='Admins',
        all_events=True,
        can_change_organizer_settings=True,
        can_create_events=True,
    )
    team.members.add(test_user)
    return organizer

@pytest.fixture
def other_orga(test_user):
    """Create a second organizer with test user access."""
    organizer = Organizer.objects.create(name='Other Orga', slug='other-orga')
    team = organizer.teams.create(
        name='Admins',
        all_events=True,
        can_change_organizer_settings=True,
        can_create_events=True,
    )
    team.members.add(test_user)
    return organizer

@pytest.fixture
def other_orga_event(other_orga):
    """Create an event under the second organizer."""
    with scopes_disabled():
        return Event.objects.create(
            organizer=other_orga,
            name='Event 3',
            slug='e3',
            date_from=now() + timedelta(days=30),
            live=True,
        )

@pytest.fixture
def events_with_stats(orga, test_user):
    """Create events with submissions and speakers for stats testing."""
    with scopes_disabled():
        starts = now() + timedelta(days=30)
        e1 = Event.objects.create(organizer=orga, name='Event 1', slug='e1', date_from=starts, live=True)
        e2 = Event.objects.create(organizer=orga, name='Event 2', slug='e2', date_from=starts, live=True)

        sub_type = SubmissionType.objects.create(event=e1, name='Talk')

        # Event 1: 1 confirmed session, 1 draft session
        s1 = Submission.objects.create(event=e1, submission_type=sub_type, title='S1', state=SubmissionStates.CONFIRMED)
        s2 = Submission.objects.create(event=e1, submission_type=sub_type, title='S2', state=SubmissionStates.DRAFT)

        # Event 1: speakers
        # Speaker 1 on confirmed session
        SpeakerRole.objects.create(submission=s1, user=test_user)
        # Speaker 2 on draft session (should be excluded)
        u2 = User.objects.create_user('s2@example.com', 'password')
        SpeakerRole.objects.create(submission=s2, user=u2)
        # Speaker 1 also on draft session (should still be counted once)
        SpeakerRole.objects.create(submission=s2, user=test_user)

        # Event 2: 0 sessions, 0 speakers

        return e1, e2

@pytest.mark.django_db
class TestEventListStats:
    """Test suite for event list stats and organizer filter interactions."""
    def test_orga_event_list_stats(self, client, test_user, events_with_stats):
        """Verify statistics and searchable select markup in event list."""
        client.force_login(test_user)
        response = client.get('/common/events/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'data-searchable-select' in content
        assert 'data-search-placeholder="Search organizers"' in content
        assert 'All organizers</option>' in content
        assert 'Stats Orga</option>' in content
        assert 'data-model-select2' not in content

        # Check the context for the injected stats
        events = response.context['events']
        events_dict = {e.slug: e for e in events}

        e1 = events_dict['e1']
        assert hasattr(e1, 'session_counts')
        assert hasattr(e1, 'speaker_counts')

        # Check session counts
        assert e1.session_counts[SubmissionStates.CONFIRMED] == 1
        assert e1.session_counts.get(SubmissionStates.DRAFT, 0) == 0  # Not counted or zero based on implementation

        # Check speaker counts
        assert e1.speaker_counts[SubmissionStates.CONFIRMED] == 1
        assert e1.speaker_counts['total'] == 1

        e2 = events_dict['e2']
        assert e2.session_counts.get(SubmissionStates.CONFIRMED, 0) == 0
        assert e2.speaker_counts.get('total', 0) == 0

    def test_admin_event_list_stats(self, admin_client, events_with_stats):
        """Verify statistics in admin event list."""
        response = admin_client.get('/admin/events/')
        assert response.status_code == 200

        events = response.context['events']
        events_dict = {e.slug: e for e in events}

        e1 = events_dict['e1']
        assert hasattr(e1, 'session_counts')
        assert hasattr(e1, 'speaker_counts')

        assert e1.session_counts[SubmissionStates.CONFIRMED] == 1
        assert e1.speaker_counts[SubmissionStates.CONFIRMED] == 1
        assert e1.speaker_counts['total'] == 1

        e2 = events_dict['e2']
        assert e2.session_counts.get(SubmissionStates.CONFIRMED, 0) == 0
        assert e2.speaker_counts.get('total', 0) == 0

    def test_orga_event_list_filter_by_organizer_submission(
        self, client, test_user, orga, other_orga, events_with_stats, other_orga_event
    ):
        """Verify choosing an organizer, clearing selection, and submitting GET form preserve parameters and results."""
        client.force_login(test_user)
        orga_id = str(orga.pk)
        other_orga_id = str(other_orga.pk)

        # 1. Base list without filter
        response = client.get('/common/events/')
        assert response.status_code == 200
        events = response.context['events']
        event_slugs = {e.slug for e in events}
        assert {'e1', 'e2', 'e3'}.issubset(event_slugs)
        content = response.content.decode()
        assert 'value="" selected>All organizers' in content
        assert f'value="{orga_id}">Stats Orga' in content
        assert f'value="{other_orga_id}">Other Orga' in content

        # 2. Filter by stats-orga via GET form submission
        response_filtered = client.get('/common/events/', {'organizer': orga_id})
        assert response_filtered.status_code == 200
        assert response_filtered.wsgi_request.GET.get('organizer') == orga_id
        filtered_events = response_filtered.context['events']
        filtered_slugs = {e.slug for e in filtered_events}
        assert 'e1' in filtered_slugs
        assert 'e2' in filtered_slugs
        assert 'e3' not in filtered_slugs
        content_filtered = response_filtered.content.decode()
        assert f'value="{orga_id}" selected' in content_filtered
        assert f'value="{other_orga_id}" selected' not in content_filtered

        # 3. Filter by other-orga via GET form submission
        response_other = client.get('/common/events/', {'organizer': other_orga_id})
        assert response_other.status_code == 200
        assert response_other.wsgi_request.GET.get('organizer') == other_orga_id
        other_events = response_other.context['events']
        other_slugs = {e.slug for e in other_events}
        assert 'e3' in other_slugs
        assert 'e1' not in other_slugs
        assert 'e2' not in other_slugs
        content_other = response_other.content.decode()
        assert f'value="{other_orga_id}" selected' in content_other
        assert f'value="{orga_id}" selected' not in content_other

        # 4. Clear selection via empty query parameter
        response_cleared = client.get('/common/events/', {'organizer': ''})
        assert response_cleared.status_code == 200
        assert response_cleared.wsgi_request.GET.get('organizer') == ''
        cleared_events = response_cleared.context['events']
        cleared_slugs = {e.slug for e in cleared_events}
        assert {'e1', 'e2', 'e3'}.issubset(cleared_slugs)
        content_cleared = response_cleared.content.decode()
        assert 'value="" selected>All organizers' in content_cleared
