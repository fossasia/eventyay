import json

import pytest
from django.core.files.base import ContentFile
from django_scopes import scope

from eventyay.api.serializers.speaker_information import SpeakerInformationSerializer
from eventyay.base.models import CachedFile


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


@pytest.mark.django_db
def test_orga_can_update_speaker_information_resource(
    client, orga_user_write_token, event
):
    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    response = client.post(
        event.api_urls.speaker_information,
        follow=True,
        data={
            "title": "Info with Resource",
            "text": "Initial text",
            "target_group": "accepted",
            "resource": f"file:{first_file.pk}",
        },
        content_type="application/json",
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
        },
    )
    assert response.status_code == 201, response.text
    info_id = response.data["id"]

    with scope(event=event):
        speaker_info = event.information.get(pk=info_id)
        assert speaker_info.resource is not None
        assert speaker_info.resource.name.endswith(".pdf")
        assert speaker_info.resource.read() == b"First PDF content"
        initial_resource_path = speaker_info.resource.name

    second_file = CachedFile.objects.create(
        filename="second.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    second_file.file.save("second.pdf", ContentFile(b"Second PDF content"))

    # PATCH existing speaker information entry with the second file
    response = client.patch(
        event.api_urls.speaker_information + f"{info_id}/",
        follow=True,
        data=json.dumps({"resource": f"file:{second_file.pk}"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["resource"].startswith("http")
    assert content["resource"].endswith(".pdf")

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.resource.name != initial_resource_path
        assert speaker_info.resource.name.endswith(".pdf")
        assert speaker_info.resource.read() == b"Second PDF content"
        current_resource_path = speaker_info.resource.name

    # Verify ordinary partial update works without modifying the attached resource
    response = client.patch(
        event.api_urls.speaker_information + f"{info_id}/",
        follow=True,
        data=json.dumps({"title": "Updated Title Only"}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Updated Title Only"
        assert speaker_info.resource.name == current_resource_path
        assert speaker_info.resource.read() == b"Second PDF content"


@pytest.mark.django_db
def test_update_speaker_information_storage_failure_rolls_back(
    client, orga_user_write_token, event, monkeypatch
):
    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Original Title",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)
        initial_path = speaker_info.resource.name

    second_file = CachedFile.objects.create(
        filename="second.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    second_file.file.save("second.pdf", ContentFile(b"Second PDF content"))

    from django.db.models.fields.files import FieldFile
    orig_save = FieldFile.save

    def failing_save(self, name, content, save=True):
        if not save:
            raise OSError("Simulated storage failure: disk full")
        return orig_save(self, name, content, save=save)

    monkeypatch.setattr(FieldFile, "save", failing_save)

    with pytest.raises(OSError, match="Simulated storage failure"):
        client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({
                "title": "New Title That Should Roll Back",
                "resource": f"file:{second_file.pk}",
            }),
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
                "Content-Type": "application/json",
            },
        )

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Original Title"
        assert speaker_info.resource.name == initial_path
        assert speaker_info.resource.read() == b"First PDF content"


@pytest.mark.django_db
def test_update_speaker_information_db_failure_cleans_up_new_file(
    client, orga_user_write_token, event, monkeypatch
):
    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Original Title",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)
        initial_path = speaker_info.resource.name
        initial_storage = speaker_info.resource.storage

    assert initial_storage.exists(initial_path)

    second_file = CachedFile.objects.create(
        filename="second.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    second_file.file.save("second.pdf", ContentFile(b"Second PDF content"))

    from django.db import DatabaseError

    from eventyay.base.models.information import SpeakerInformation

    orig_save = SpeakerInformation.save
    saved_new_paths = []

    def failing_save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields and "resource" in update_fields:
            saved_new_paths.append(self.resource.name)
            raise DatabaseError("Simulated database failure during resource save")
        return orig_save(self, *args, **kwargs)

    monkeypatch.setattr(SpeakerInformation, "save", failing_save)

    with pytest.raises(DatabaseError, match="Simulated database failure"):
        client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({
                "title": "Title Should Roll Back",
                "resource": f"file:{second_file.pk}",
            }),
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
                "Content-Type": "application/json",
            },
        )

    # Verify database rollback
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Original Title"
        assert speaker_info.resource.name == initial_path

    # Verify existing resource was not deleted
    assert initial_storage.exists(initial_path)

    # Verify newly written file was cleaned up from storage
    assert len(saved_new_paths) == 1
    new_path = saved_new_paths[0]
    assert new_path != initial_path
    assert not initial_storage.exists(new_path)


@pytest.mark.django_db
def test_speaker_information_task_cleanup_file_deletes_old_file_and_preserves_current(
    event,
):
    from django.core.files.storage import default_storage

    from eventyay.common.tasks import task_cleanup_file

    with scope(event=event):
        speaker_info = event.information.create(
            title="Cleanup Test Info",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save(
            "current.pdf", ContentFile(b"Current file content"), save=True
        )
        current_path = speaker_info.resource.path

    # Create an old orphan file that was replaced
    old_path = default_storage.save(
        f"{event.slug}/speaker_information/old_orphan.pdf",
        ContentFile(b"Old file content"),
    )
    old_abs_path = default_storage.path(old_path)
    assert default_storage.exists(old_path)
    assert default_storage.exists(current_path)

    # 1. Run task_cleanup_file for the old replaced path -> should delete it
    task_cleanup_file(
        model="Speakerinformation",
        pk=speaker_info.pk,
        field="resource",
        path=old_abs_path,
    )
    assert not default_storage.exists(old_path)
    assert default_storage.exists(current_path)

    # 2. Safety check: Run task_cleanup_file pointing to CURRENT file -> must NOT delete it
    task_cleanup_file(
        model="Speakerinformation",
        pk=speaker_info.pk,
        field="resource",
        path=current_path,
    )
    assert default_storage.exists(current_path)


@pytest.mark.django_db
def test_update_speaker_information_enqueue_failure_does_not_abort_request(
    client, orga_user_write_token, event, monkeypatch, caplog
):

    from eventyay.common.tasks import task_cleanup_file

    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Initial Title",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)

    second_file = CachedFile.objects.create(
        filename="second.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    second_file.file.save("second.pdf", ContentFile(b"Second PDF content"))

    def broken_apply_async(*args, **kwargs):
        raise ConnectionError("Simulated Celery broker connection failure")

    monkeypatch.setattr(task_cleanup_file, "apply_async", broken_apply_async)

    from django.test import TestCase

    tc = TestCase()
    with caplog.at_level("WARNING"):
        with tc.captureOnCommitCallbacks(execute=True):
            response = client.patch(
                event.api_urls.speaker_information + f"{speaker_info.pk}/",
                follow=True,
                data=json.dumps({"resource": f"file:{second_file.pk}"}),
                headers={
                    "Authorization": f"Token {orga_user_write_token.token}",
                    "Content-Type": "application/json",
                },
            )

    assert response.status_code == 200, response.text

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.resource.read() == b"Second PDF content"

    # Verify enqueue failure was logged with context
    assert any(
        "Failed to enqueue cleanup task" in record.message
        for record in caplog.records
    )


@pytest.mark.django_db
def test_orga_can_clear_speaker_information_resource(
    client, orga_user_write_token, event
):
    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Info with Resource",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.resource is not None
        assert bool(speaker_info.resource) is True

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"resource": None}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["resource"] is None

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert not speaker_info.resource
        assert speaker_info.resource.name == ""


@pytest.mark.django_db
def test_orga_can_clear_already_empty_speaker_information_resource(
    client, orga_user_write_token, event
):
    with scope(event=event):
        speaker_info = event.information.create(
            title="Info without Resource",
            text="Initial text",
            target_group="accepted",
        )

    response = client.patch(
        event.api_urls.speaker_information + f"{speaker_info.pk}/",
        follow=True,
        data=json.dumps({"resource": None}),
        headers={
            "Authorization": f"Token {orga_user_write_token.token}",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content["resource"] is None

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert not speaker_info.resource


@pytest.mark.django_db
def test_clear_speaker_information_resource_cleanup_post_commit_not_before(
    client, orga_user_write_token, event
):
    from django.test import TestCase

    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Info with Resource",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)
        initial_path = speaker_info.resource.name
        storage = speaker_info.resource.storage

    assert storage.exists(initial_path)

    tc = TestCase()
    with tc.captureOnCommitCallbacks(execute=False) as callbacks:
        response = client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({"resource": None}),
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200, response.text
        # Before callbacks execute (prior to commit completion), file still exists
        assert storage.exists(initial_path)

    # Post-commit callback enqueues cleanup which deletes the old file
    assert len(callbacks) >= 1
    for cb in callbacks:
        cb()
    assert not storage.exists(initial_path)

    with scope(event=event):
        speaker_info.refresh_from_db()
        assert not speaker_info.resource


@pytest.mark.django_db
def test_clear_speaker_information_resource_db_failure_rolls_back_and_preserves_file(
    client, orga_user_write_token, event, monkeypatch
):
    from django.db import DatabaseError

    from eventyay.base.models.information import SpeakerInformation

    session_key = (
        f"api-upload-{str(type(orga_user_write_token.user))}-{orga_user_write_token.user.pk}"
    )
    first_file = CachedFile.objects.create(
        filename="first.pdf",
        type="application/pdf",
        session_key=session_key,
    )
    first_file.file.save("first.pdf", ContentFile(b"First PDF content"))

    with scope(event=event):
        speaker_info = event.information.create(
            title="Original Title",
            text="Initial text",
            target_group="accepted",
        )
        speaker_info.resource.save("first.pdf", first_file.file, save=True)
        initial_path = speaker_info.resource.name
        initial_storage = speaker_info.resource.storage

    assert initial_storage.exists(initial_path)

    orig_save = SpeakerInformation.save

    def failing_save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields and "resource" in update_fields and not self.resource:
            raise DatabaseError("Simulated database failure during resource clear")
        return orig_save(self, *args, **kwargs)

    monkeypatch.setattr(SpeakerInformation, "save", failing_save)

    with pytest.raises(DatabaseError, match="Simulated database failure during resource clear"):
        client.patch(
            event.api_urls.speaker_information + f"{speaker_info.pk}/",
            follow=True,
            data=json.dumps({
                "title": "Title Should Roll Back",
                "resource": None,
            }),
            headers={
                "Authorization": f"Token {orga_user_write_token.token}",
                "Content-Type": "application/json",
            },
        )

    # Verify database rollback
    with scope(event=event):
        speaker_info.refresh_from_db()
        assert speaker_info.title == "Original Title"
        assert speaker_info.resource.name == initial_path
        assert speaker_info.resource.read() == b"First PDF content"

    # Verify existing file was not deleted
    assert initial_storage.exists(initial_path)
