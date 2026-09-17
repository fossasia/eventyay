from datetime import timedelta

import pytest
from django.utils.timezone import localtime, now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer


SASH = 'class="startpage-event-ongoing"'


def create_event(organizer, slug, date_from, date_to):
    return Event.objects.create(
        organizer=organizer,
        name=slug,
        slug=slug,
        date_from=date_from,
        date_to=date_to,
        live=True,
        is_public=True,
        startpage_visible=True,
    )


def card_for(content, slug):
    return next(card for card in content.split('<article')[1:] if f'/{slug}/' in card)


@pytest.fixture
def organizer():
    with scopes_disabled():
        return Organizer.objects.create(name='Test Organizer', slug='test-org')


@pytest.fixture
def upcoming_event(organizer):
    with scopes_disabled():
        return create_event(organizer, 'upcoming', now() + timedelta(days=10), now() + timedelta(days=12))


@pytest.fixture
def ongoing_event(organizer):
    with scopes_disabled():
        return create_event(organizer, 'ongoing', now() - timedelta(days=2), now() + timedelta(days=2))


@pytest.mark.django_db
def test_startpage_marks_only_ongoing_events(client, ongoing_event, upcoming_event):
    content = client.get('/').content.decode()

    assert SASH in card_for(content, 'ongoing')
    assert SASH not in card_for(content, 'upcoming')
    assert '<h2>Upcoming and ongoing events</h2>' in content


@pytest.mark.django_db
def test_startpage_keeps_upcoming_heading_without_ongoing_events(client, upcoming_event):
    content = client.get('/').content.decode()

    assert SASH not in content
    assert '<h2>Upcoming events</h2>' in content


@pytest.mark.django_db
def test_startpage_does_not_mark_event_that_ended_today(client, organizer):
    current = now()
    midnight = localtime(current).replace(hour=0, minute=0, second=0, microsecond=0)
    with scopes_disabled():
        create_event(organizer, 'ended-today', midnight, midnight + (current - midnight) / 2)

    content = client.get('/').content.decode()

    assert SASH not in card_for(content, 'ended-today')
    assert '<h2>Upcoming events</h2>' in content


@pytest.mark.django_db
def test_upcoming_page_heading_follows_ongoing_events(client, ongoing_event, upcoming_event):
    response = client.get('/upcoming/')
    content = response.content.decode()

    assert response.context['has_ongoing']
    assert 'Upcoming and Ongoing Events' in content
    assert SASH in card_for(content, 'ongoing')

    with scopes_disabled():
        Event.objects.filter(pk=ongoing_event.pk).update(
            date_from=now() + timedelta(days=3), date_to=now() + timedelta(days=4)
        )

    assert not client.get('/upcoming/').context['has_ongoing']


@pytest.mark.django_db
def test_upcoming_page_keeps_cfp_heading_with_ongoing_events(client, ongoing_event):
    content = client.get('/upcoming/?cfp=open').content.decode()

    assert 'Open calls for proposals' in content
    assert 'Upcoming and Ongoing Events' not in content
