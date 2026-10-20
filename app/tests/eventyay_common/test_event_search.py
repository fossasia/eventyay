from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User


@pytest.mark.django_db
def test_event_search_applies_permission_filter_before_limit(client):
    with scopes_disabled():
        user = User.objects.create_user('searchuser@eventyay.com', 'testpassword')
        organizer = Organizer.objects.create(name='Search Organizer', slug='search-organizer')
        team = Team.objects.create(organizer=organizer, name='Orders Team', can_view_orders=True)
        team.members.add(user)

        now = timezone.now()
        for index in range(10):
            Event.objects.create(
                organizer=organizer,
                name=f'Search Sentinel {index:02d}',
                slug=f'search-sentinel-{index:02d}',
                date_from=now + timedelta(days=30),
                date_to=now + timedelta(days=32),
                currency='USD',
                locale='en',
            )
        authorized_event = Event.objects.create(
            organizer=organizer,
            name='Search Sentinel 99',
            slug='search-sentinel-99',
            date_from=now + timedelta(days=30),
            date_to=now + timedelta(days=32),
            currency='USD',
            locale='en',
        )
        team.limit_events.add(authorized_event)

    client.force_login(user)
    response = client.get(reverse('eventyay_common:events.search'), {'query': 'Search Sentinel'})

    assert response.status_code == 200
    assert response.json() == [
        {'name': authorized_event.name, 'slug': authorized_event.slug, 'organizer': organizer.slug}
    ]
