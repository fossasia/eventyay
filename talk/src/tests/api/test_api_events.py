import json

import pytest

from pretalx.api.serializers.event import EventListSerializer, EventSerializer


@pytest.mark.django_db
def test_event_list_serializer(event):
    data = EventListSerializer(event).data
    assert data == {
        "name": {"en": event.name},
        "slug": event.slug,
        "live": event.live,
        "date_from": event.date_from.isoformat(),
        "date_to": event.date_to.isoformat(),
        "timezone": event.timezone,
    }


@pytest.mark.django_db
def test_event_serializer(event):
    data = EventSerializer(event).data
    assert data == {
        "name": {"en": event.name},
        "slug": event.slug,
        "live": event.live,
        "date_from": event.date_from.isoformat(),
        "date_to": event.date_to.isoformat(),
        "timezone": event.timezone,
        "email": event.email,
        "primary_color": event.primary_color,
        "custom_domain": event.custom_domain,
        "logo": None,
        "header_image": None,
        "locale": event.locale,
        "locales": event.locales,
        "content_locales": event.content_locales,
    }


@pytest.mark.django_db
def test_can_only_see_live_events(client, event, other_event):
    other_event.live = False
    other_event.save()
    assert event.live
    assert not other_event.live

    response = client.get("/api/events/")
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content) == 1, content
    assert content[0]["name"]["en"] == event.name


@pytest.mark.django_db
def test_can_only_see_live_events_in_detail(client, event):
    assert event.live
    response = client.get(event.api_urls.base, follow=True)
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["name"]["en"] == event.name

    event.live = False
    event.save()

    response = client.get(event.api_urls.base, follow=True)
    assert response.status_code == 404
    assert event.name not in response.text


@pytest.mark.django_db
def test_orga_can_see_nonlive_events(client, event, other_event, orga_user_token):
    event.live = False
    event.save()
    assert not event.live
    assert other_event.live

    response = client.get(
        "/api/events/", headers={"Authorization": f"Token {orga_user_token.token}"}
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert len(content) == 2, content
    assert content[-1]["name"]["en"] == event.name
