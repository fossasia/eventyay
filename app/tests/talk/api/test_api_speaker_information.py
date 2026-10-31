import json

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django_scopes import scope

from eventyay.api.serializers.speaker_information import SpeakerInformationSerializer
from eventyay.base.models import TeamAPIToken
from eventyay.common.tasks import task_cleanup_file


@pytest.mark.django_db
def test_speaker_information_serializer(submission_type, event, track):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
        speaker_info.limit_tracks.add(track)
        speaker_info.limit_types.add(submission_type)

        data = SpeakerInformationSerializer(
            speaker_info, context={"event": speaker_info.event}
        ).data

        assert set(data.keys()) == {
            "id",
            "target_group",
            "title",
            "text",
            "resource",
            "limit_tracks",
            "limit_types",
        }
        assert data["target_group"] == "accepted"
        assert track.pk in data["limit_tracks"]
        assert submission_type.pk in data["limit_types"]


@pytest.mark.parametrize("is_public", (True, False))
@pytest.mark.django_db
def test_cannot_see_speaker_information(client, event, is_public):
    with scope(event=event):
        event.is_public = is_public
        event.save()
    response = client.get(event.api_urls.speaker_information, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_speaker_information(client, orga_user_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
    response = client.get(
        event.api_urls.speaker_information,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["title"]["en"] == speaker_info.title


@pytest.mark.django_db
def test_orga_can_see_single_speaker_information(client, orga_user_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
    response = client.get(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["title"]["en"] == speaker_info.title


@pytest.mark.django_db
def test_no_legacy_speaker_information_api(client, orga_user_token, event):
    from eventyay.api.versions import LEGACY

    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
        )
    response = client.get(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Pretalx-Version": LEGACY,
        },
    )
    assert response.status_code == 400, response.text
    assert "API version not supported." in response.text


@pytest.mark.django_db
def test_orga_can_create_speaker_information(client, orga_user_write_token, event):
    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
            "foo": "bar",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    with scope(event=event):
        speaker_info = event.information.all().first()
        assert speaker_info.title == "New Test Info"
        assert speaker_info.text == "This is some new test information"
        assert (
            speaker_info.logged_actions()
            .filter(action_type="eventyay.speaker_information.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_create_speaker_information_readonly_token(
    client, orga_user_token, event
):
    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_token.token}",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        assert not event.information.filter(title="New Test Info").exists()
        assert (
            not event.logged_actions()
            .filter(action_type="eventyay.speaker_information.create")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_update_speaker_information(client, orga_user_write_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"title": "Updated Test Info"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Updated Test Info"
        assert (
            speaker_info.logged_actions()
            .filter(action_type="eventyay.speaker_information.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_update_speaker_information_readonly_token(
    client, orga_user_token, event
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"title": "Updated Test Info"}),
        headers={
            "Authorization": f"Token {orga_user_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 403
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title != "Updated Test Info"
        assert (
            not speaker_info.logged_actions()
            .filter(action_type="eventyay.speaker_information.update")
            .exists()
        )


@pytest.mark.django_db
def test_orga_can_delete_speaker_information(client, orga_user_write_token, event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.delete(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 204
    with scope(event=event):
        assert not event.information.filter(pk=speaker_info.pk).exists()
        assert (
            event.logged_actions()
            .filter(action_type="eventyay.speaker_information.delete")
            .exists()
        )


@pytest.mark.django_db
def test_orga_cannot_delete_speaker_information_readonly_token(
    client, orga_user_token, event
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )

    response = client.delete(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        assert event.information.filter(pk=speaker_info.pk).exists()


@pytest.mark.django_db
def test_orga_can_expand_related_fields(
    client, orga_user_token, event, submission_type
):
    with scope(event=event):
        track = event.tracks.create(name="Test Track")
        speaker_info = event.information.create(
            title="Test Info",
            text="This is some test information",
            target_group="accepted",
        )
        speaker_info.limit_tracks.add(track)
        speaker_info.limit_types.add(submission_type)

    response = client.get(
        event.api_urls.speaker_information
        + f"{speaker_info.pk}/?expand=limit_tracks,limit_types",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["title"]["en"] == "Test Info"
    assert content["limit_tracks"][0]["name"]["en"] == "Test Track"
    assert content["limit_types"][0]["name"]["en"] == submission_type.name


@pytest.mark.django_db
def test_orga_can_create_speaker_information_with_resource(
    client, orga_user_write_token, event
):
    response = client.post(
        "/api/upload/",
        data={"file": ContentFile("Test PDF content", name="test.pdf")},
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Disposition": 'attachment; filename="test.pdf"',
            "Content-Type": "application/pdf",
        },
    )
    assert response.status_code == 201, response.text
    file_id = response.data["id"]
    assert file_id.startswith("file:")

    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "Info with Resource",
            "text": "This information has an attached resource",
            "target_group": "accepted",
            "resource": file_id,
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text

    with scope(event=event):
        speaker_info = event.information.get(title="Info with Resource")
        assert speaker_info.resource is not None
        assert speaker_info.resource.name.endswith(".pdf")

        response = client.get(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
            },
        )
        content = json.loads(response.text)
        assert response.status_code == 200
        assert content["resource"].startswith("http")
        assert content["resource"].endswith(".pdf")


@pytest.fixture
def upload_token(orga_user, event):
    team = event.organizer.teams.filter(members=orga_user).first()
    return TeamAPIToken.objects.create(team=team, name="upload-token")


def upload_pdf(client, token, content):
    response = client.post(
        "/api/v1/upload",
        data=content,
        content_type="application/pdf",
        headers={
            "Authorization": f"Token {token.token}",
            "Content-Disposition": 'attachment; filename="new.pdf"',
        },
    )
    assert response.status_code == 201, response.text
    return response.data["id"]


@pytest.mark.django_db
def test_orga_can_replace_speaker_information_resource(
    client, upload_token, event, mocker, django_capture_on_commit_callbacks
):
    cleanup = mocker.spy(task_cleanup_file, "apply_async")
    with scope(event=event):
        speaker_info = event.information.create(
            title="Info with Resource",
            text="This information has an attached resource",
            target_group="accepted",
            resource=ContentFile(b"old content", name="old.pdf"),
        )
    old_name = speaker_info.resource.name
    file_id = upload_pdf(client, upload_token, b"new content")

    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({"resource": file_id}),
            headers={
                "Authorization": f"Token {upload_token.token}",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code == 200, response.text
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.resource.name != old_name
        with speaker_info.resource.open("rb") as resource:
            assert resource.read() == b"new content"
    assert not default_storage.exists(old_name)
    assert cleanup.call_args.kwargs["kwargs"]["event_id"] == event.pk


@pytest.mark.django_db
def test_cleanup_file_skips_speaker_information_from_other_event(event, other_event):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Info with Resource",
            text="This information has an attached resource",
            target_group="accepted",
            resource=ContentFile(b"old content", name="old.pdf"),
        )
        old_name = speaker_info.resource.name
        old_path = speaker_info.resource.path
        speaker_info.resource.save("new.pdf", ContentFile(b"new content"))

    task_cleanup_file(
        model="SpeakerInformation",
        pk=speaker_info.pk,
        field="resource",
        path=old_path,
        event_id=other_event.pk,
    )

    assert default_storage.exists(old_name)


@pytest.mark.django_db
def test_failed_resource_save_rolls_back_speaker_information_update(
    client, upload_token, event, mocker
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Info with Resource",
            text="This information has an attached resource",
            target_group="accepted",
        )
    file_id = upload_pdf(client, upload_token, b"new content")
    mocker.patch(
        "django.db.models.fields.files.FieldFile.save",
        side_effect=OSError("storage unavailable"),
    )

    with pytest.raises(OSError):
        client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({"title": "Updated title", "resource": file_id}),
            headers={
                "Authorization": f"Token {upload_token.token}",
                "Content-Type": "application/json",
            },
        )

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Info with Resource"


@pytest.mark.django_db
def test_orga_cannot_assign_track_from_other_event(
    client, orga_user_write_token, event, other_event
):
    with scope(event=other_event):
        other_track = other_event.tracks.create(name="Other Track")

    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "New Test Info",
            "text": "This is some new test information",
            "target_group": "accepted",
            "limit_tracks": [other_track.pk],
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )

    assert response.status_code == 400, response.text
    assert "limit_tracks" in json.loads(response.text)

    with scope(event=event):
        assert not event.information.filter(title="New Test Info").exists()
