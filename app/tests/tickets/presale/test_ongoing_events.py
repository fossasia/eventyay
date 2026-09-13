from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, SubEvent


@pytest.fixture
def test_organizer():
    with scopes_disabled():
        return Organizer.objects.create(name='Ongoing Org', slug='ongoing-org')


@pytest.mark.django_db
def test_event_is_ongoing_property(test_organizer):
    current = now()
    with scopes_disabled():
        # Ongoing event with date_from and date_to
        ongoing_event = Event.objects.create(
            organizer=test_organizer,
            name='Ongoing Event',
            slug='ongoing-ev',
            date_from=current - timedelta(days=2),
            date_to=current + timedelta(days=2),
            live=True,
            is_public=True,
        )
        assert ongoing_event.is_ongoing is True

        # Future event
        future_event = Event.objects.create(
            organizer=test_organizer,
            name='Future Event',
            slug='future-ev',
            date_from=current + timedelta(days=1),
            date_to=current + timedelta(days=3),
            live=True,
            is_public=True,
        )
        assert future_event.is_ongoing is False

        # Past event
        past_event = Event.objects.create(
            organizer=test_organizer,
            name='Past Event',
            slug='past-ev',
            date_from=current - timedelta(days=5),
            date_to=current - timedelta(days=2),
            live=True,
            is_public=True,
        )
        assert past_event.is_ongoing is False

        # Single-day event today without date_to
        today_event = Event.objects.create(
            organizer=test_organizer,
            name='Today Event',
            slug='today-ev',
            date_from=current - timedelta(hours=1),
            date_to=None,
            live=True,
            is_public=True,
        )
        assert today_event.is_ongoing is True

        # Single-day event yesterday without date_to
        yesterday_event = Event.objects.create(
            organizer=test_organizer,
            name='Yesterday Event',
            slug='yesterday-ev',
            date_from=current - timedelta(days=1, hours=2),
            date_to=None,
            live=True,
            is_public=True,
        )
        assert yesterday_event.is_ongoing is False

        # Series event with subevents
        series_event = Event.objects.create(
            organizer=test_organizer,
            name='Series Event',
            slug='series-ev',
            date_from=current + timedelta(days=5),
            has_subevents=True,
            live=True,
            is_public=True,
        )
        assert series_event.is_ongoing is False

        subevent = SubEvent.objects.create(
            event=series_event,
            name='SubEvent 1',
            date_from=current - timedelta(days=1),
            date_to=current + timedelta(days=1),
            active=True,
        )
        assert subevent.is_ongoing is True
        assert series_event.is_ongoing is True


@pytest.mark.django_db
def test_startpage_ongoing_section_header_and_badge(test_organizer, client):
    current = now()
    with scopes_disabled():
        # Only future event initially
        future_ev = Event.objects.create(
            organizer=test_organizer,
            name='Future Conference',
            slug='future-conf',
            date_from=current + timedelta(days=10),
            date_to=current + timedelta(days=12),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )

    # When no ongoing events exist
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Upcoming events' in content
    assert 'Upcoming and ongoing events' not in content
    assert 'startpage-sash-ribbon' not in content

    # Add an ongoing event
    with scopes_disabled():
        ongoing_ev = Event.objects.create(
            organizer=test_organizer,
            name='Active Live Festival',
            slug='active-live-festival',
            date_from=current - timedelta(days=1),
            date_to=current + timedelta(days=2),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )

    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Upcoming and ongoing events' in content
    assert 'startpage-sash-ribbon' in content
    assert 'Ongoing' in content
    assert 'is-ongoing' in content


@pytest.mark.django_db
def test_upcoming_events_page_ongoing_header_and_badge(test_organizer, client):
    current = now()
    with scopes_disabled():
        Event.objects.create(
            organizer=test_organizer,
            name='Ongoing Hackathon',
            slug='ongoing-hackathon',
            date_from=current - timedelta(hours=5),
            date_to=current + timedelta(days=2),
            live=True,
            is_public=True,
            startpage_visible=True,
        )

    response = client.get('/upcoming/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Upcoming and Ongoing Events' in content
    assert 'startpage-sash-ribbon' in content
    assert 'Ongoing' in content
