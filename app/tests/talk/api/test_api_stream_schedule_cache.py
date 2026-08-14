import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule


@pytest.fixture
def active_stream(room):
    with scope(event=room.event):
        stream = StreamSchedule(
            room=room,
            title="Active Stream",
            url="https://example.com/stream",
            start_time=now() - timedelta(minutes=5),
            end_time=now() + timedelta(minutes=30),
        )
        stream.save(skip_validation=True)
        return stream


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_current_stream_returns_active_stream(client, orga_user_token, room, active_stream):
    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["id"] == active_stream.pk
    assert content["title"] == "Active Stream"


@pytest.mark.django_db
def test_current_stream_returns_404_without_active_stream(client, orga_user_token, room):
    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_current_stream_sets_cache_headers(client, orga_user_token, room, active_stream):
    response = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    assert response.status_code == 200
    assert response.headers.get("ETag") is not None
    assert response.headers.get("Last-Modified") is not None


@pytest.mark.django_db
def test_current_stream_populates_cache(client, orga_user_token, room, active_stream):
    cache_key = f"stream:current:{room.pk}"
    assert cache.get(cache_key) is None

    client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    cached = cache.get(cache_key)
    assert cached is not None
    assert cached["data"]["id"] == active_stream.pk


@pytest.mark.django_db
def test_current_stream_cache_hit_returns_same_etag(client, orga_user_token, room, active_stream):
    response1 = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    response2 = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.headers.get("ETag") == response2.headers.get("ETag")


@pytest.mark.django_db
def test_current_stream_returns_304_when_etag_matches(client, orga_user_token, room, active_stream):
    first = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    etag = first.headers.get("ETag")

    second = client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "If-None-Match": etag,
        },
    )

    assert second.status_code == 304


@pytest.mark.django_db
def test_saving_stream_schedule_clears_cache(client, orga_user_token, room, active_stream):
    cache_key = f"stream:current:{room.pk}"

    client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert cache.get(cache_key) is not None

    with scope(event=room.event):
        active_stream.title = "Updated Title"
        active_stream.save(skip_validation=True)

    assert cache.get(cache_key) is None


@pytest.mark.django_db
def test_deleting_stream_schedule_clears_cache(client, orga_user_token, room, active_stream):
    cache_key = f"stream:current:{room.pk}"

    client.get(
        room.event.api_urls.rooms + f"{room.pk}/streams/current/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert cache.get(cache_key) is not None

    with scope(event=room.event):
        active_stream.delete()

    assert cache.get(cache_key) is None