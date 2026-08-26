from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer


@pytest.fixture
def startpage_events():
    with scopes_disabled():
        o = Organizer.objects.create(name='Test Organizer', slug='test-org')
        # Create featured event
        e_featured = Event.objects.create(
            organizer=o,
            name='Featured Event',
            slug='featured-1',
            date_from=now() + timedelta(days=5),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=True,
        )
        e_featured.settings.set('event_preview_image', 'http://example.com/hero.jpg')
        # Create upcoming event
        e_upcoming = Event.objects.create(
            organizer=o,
            name='Upcoming Event',
            slug='upcoming-1',
            date_from=now() + timedelta(days=10),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )
        # Create past event
        e_past = Event.objects.create(
            organizer=o,
            name='Past Event',
            slug='past-1',
            date_from=now() - timedelta(days=10),
            date_to=now() - timedelta(days=9),
            live=True,
            is_public=True,
            startpage_visible=True,
            startpage_featured=False,
        )
        return o, e_featured, e_upcoming, e_past


@pytest.mark.django_db
def test_startpage_sections_rendering(startpage_events, client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Featured Event' in content
    assert 'Upcoming Event' in content
    assert 'Past Event' in content


@pytest.mark.django_db
def test_startpage_event_card_image_attributes(startpage_events, client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    # Verify performance attributes on card elements
    assert 'decoding="async"' in content
    assert 'width="800"' in content
    assert 'height="450"' in content
    assert 'fetchpriority="high"' in content or 'loading="lazy"' in content


@pytest.mark.django_db
def test_startpage_bounded_query_scaling(startpage_events, client, django_assert_num_queries):
    o = startpage_events[0]
    # Create 30 additional past events in DB
    with scopes_disabled():
        for i in range(30):
            Event.objects.create(
                organizer=o,
                name=f'Bulk Past Event {i}',
                slug=f'bulk-past-{i}',
                date_from=now() - timedelta(days=20 + i),
                date_to=now() - timedelta(days=19 + i),
                live=True,
                is_public=True,
                startpage_visible=True,
            )

    response = client.get('/')
    assert response.status_code == 200
    ctx = response.context
    assert len(ctx['past_events']) <= 8
    assert len(ctx['upcoming_events']) <= 8
    assert len(ctx['featured_events']) <= 8
