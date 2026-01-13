import json
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule


@pytest.mark.django_db
def test_list_stream_schedules_empty(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_create_stream_schedule(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    data = {
        "title": "Day 1 Stream",
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
        "stream_type": "youtube",
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["title"] == "Day 1 Stream"
    assert response_data["url"] == "https://www.youtube.com/watch?v=test123"
    assert response_data["stream_type"] == "youtube"
    assert "id" in response_data
    with scope(event=room.event):
        assert StreamSchedule.objects.filter(room=room).count() == 1


@pytest.mark.django_db
def test_create_stream_schedule_minimal(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    data = {
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["url"] == "https://www.youtube.com/watch?v=test123"
    assert response_data["title"] == ""
    assert response_data["stream_type"] == "youtube"


@pytest.mark.django_db
def test_create_stream_schedule_overlap_validation(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    start = now() + timedelta(hours=1)
    end = now() + timedelta(hours=3)
    data1 = {
        "url": "https://www.youtube.com/watch?v=test1",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }
    response1 = client.post(
        url,
        data=json.dumps(data1),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response1.status_code == 201
    data2 = {
        "url": "https://www.youtube.com/watch?v=test2",
        "start_time": (start + timedelta(hours=1)).isoformat(),
        "end_time": (end + timedelta(hours=1)).isoformat(),
    }
    response2 = client.post(
        url,
        data=json.dumps(data2),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response2.status_code == 400
    assert "overlap" in response2.json().get("__all__", [""])[0].lower()


@pytest.mark.django_db
def test_create_stream_schedule_end_before_start(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    data = {
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=3)).isoformat(),
        "end_time": (now() + timedelta(hours=1)).isoformat(),
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    assert "end_time" in response.json()


@pytest.mark.django_db
def test_list_stream_schedules_multiple(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=4),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["url"] == "https://www.youtube.com/watch?v=test1"
    assert data[1]["url"] == "https://www.youtube.com/watch?v=test2"


@pytest.mark.django_db
def test_get_current_stream_active(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/streams/current"
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == schedule.pk
    assert data["url"] == "https://www.youtube.com/watch?v=test123"


@pytest.mark.django_db
def test_get_current_stream_none(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/streams/current"
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_next_stream_upcoming(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/streams/next"
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == schedule.pk
    assert data["url"] == "https://www.youtube.com/watch?v=test123"


@pytest.mark.django_db
def test_get_next_stream_none(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/streams/next"
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_get_next_stream_returns_earliest(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/streams/next"
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == schedule1.pk


@pytest.mark.django_db
def test_stream_schedule_viewset_list(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/stream_schedules/"
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1


@pytest.mark.django_db
def test_stream_schedule_viewset_create(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/stream_schedules/"
    data = {
        "room": room.pk,
        "title": "Test Stream",
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
        "stream_type": "youtube",
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["title"] == "Test Stream"
    with scope(event=room.event):
        assert StreamSchedule.objects.filter(room=room).count() == 1


@pytest.mark.django_db
def test_stream_schedule_viewset_retrieve(client, orga_user_write_token, room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/stream_schedules/{schedule.pk}/"
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == schedule.pk
    assert data["url"] == "https://www.youtube.com/watch?v=test123"


@pytest.mark.django_db
def test_stream_schedule_viewset_update(client, orga_user_write_token, room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            title="Original Title",
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/stream_schedules/{schedule.pk}/"
    data = {
        "title": "Updated Title",
        "url": "https://www.youtube.com/watch?v=test456",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
    }
    response = client.patch(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["title"] == "Updated Title"
    assert response_data["url"] == "https://www.youtube.com/watch?v=test456"
    with scope(event=room.event):
        schedule.refresh_from_db()
        assert schedule.title == "Updated Title"
        assert schedule.url == "https://www.youtube.com/watch?v=test456"


@pytest.mark.django_db
def test_stream_schedule_viewset_delete(client, orga_user_write_token, room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/stream_schedules/{schedule.pk}/"
    response = client.delete(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 204
    with scope(event=room.event):
        assert not StreamSchedule.objects.filter(pk=schedule.pk).exists()


@pytest.mark.django_db
def test_stream_schedule_viewset_filter_by_room(client, orga_user_write_token, room, other_room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream_schedules/"
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        StreamSchedule.objects.create(
            room=other_room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
    response = client.get(
        url,
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["url"] == "https://www.youtube.com/watch?v=test1"


@pytest.mark.django_db
def test_stream_schedule_permissions_readonly_token(client, orga_user_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    data = {
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_stream_schedule_config_field(client, orga_user_write_token, room):
    url = f"/api/v1/organizers/{room.event.organizer.slug}/events/{room.event.slug}/rooms/{room.pk}/stream-schedules/"
    data = {
        "url": "https://www.youtube.com/watch?v=test123",
        "start_time": (now() + timedelta(hours=1)).isoformat(),
        "end_time": (now() + timedelta(hours=3)).isoformat(),
        "config": {"video_id": "test123", "autoplay": True},
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["config"] == {"video_id": "test123", "autoplay": True}
