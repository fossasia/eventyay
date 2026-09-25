from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from django.urls import reverse
from PIL import Image

from eventyay.base.models.storage_model import StoredFile
from eventyay.core.permissions import Permission
from eventyay.storage.views import enforce_csrf


def png_upload(name="avatar.png", size=(600, 400), mode="RGB"):
    """An upload whose payload is noisy enough to have a meaningful file size."""
    buffer = BytesIO()
    Image.effect_noise(size, 32).convert(mode).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def gif_upload(name="avatar.png"):
    """An animated GIF, which the pipeline stores without recompression."""
    frames = [Image.effect_noise((60, 60), 32).convert("P") for _ in range(3)]
    buffer = BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/gif")


@pytest.fixture
def session_client(user):
    """A client authenticated by session only, with CSRF checks turned on."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


@pytest.fixture
def granted_upload_permission(user, monkeypatch):
    """
    Grant upload permission to the session user.

    The video login service needs a fully provisioned video event, which is not what
    these tests are about, so only its permission payload is stubbed out.
    """
    monkeypatch.setattr(
        "eventyay.storage.views.login",
        lambda **kwargs: SimpleNamespace(
            user=user,
            event_config={"permissions": [Permission.ROOM_CHAT_SEND.value], "rooms": []},
        ),
    )


def upload_with_csrf_token(client, event, csrf_cookie_name, **data):
    csrftoken = get_token(RequestFactory().get("/"))
    client.cookies[csrf_cookie_name] = csrftoken
    return client.post(
        reverse("storage:upload", kwargs={"event_id": event.id}),
        data=data,
        HTTP_X_CSRFTOKEN=csrftoken,
    )


def test_enforce_csrf_rejects_missing_token():
    request = RequestFactory().post("/storage/evt/upload/")
    with pytest.raises(PermissionDenied, match="CSRF verification failed"):
        enforce_csrf(request)


@pytest.mark.django_db
def test_session_upload_rejects_missing_csrf_token(event, session_client, granted_upload_permission):
    response = session_client.post(
        reverse("storage:upload", kwargs={"event_id": event.id}),
        data={"file": png_upload()},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_session_upload_resizes_to_requested_dimensions(
    event, session_client, granted_upload_permission, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)
    upload = png_upload()

    response = upload_with_csrf_token(
        session_client, event, settings.CSRF_COOKIE_NAME, file=upload, width="96", height="96"
    )

    assert response.status_code == 201
    assert "url" in response.json()
    stored_file = StoredFile.objects.get()
    assert stored_file.type == "image/png"
    assert stored_file.file.size < upload.size
    with Image.open(stored_file.file) as stored_image:
        assert max(stored_image.size) <= 96


@pytest.mark.django_db
def test_session_upload_strips_jpeg_metadata(event, session_client, granted_upload_permission, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    image = Image.effect_noise((200, 100), 32).convert("RGB")
    exif = image.getexif()
    exif[274] = 3  # orientation: rotated by 180 degrees
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    upload = SimpleUploadedFile("photo.jpg", buffer.getvalue(), content_type="image/jpeg")

    response = upload_with_csrf_token(session_client, event, settings.CSRF_COOKIE_NAME, file=upload)

    assert response.status_code == 201
    stored_file = StoredFile.objects.get()
    assert stored_file.type == "image/jpeg"
    assert stored_file.filename == "photo.jpg"
    with Image.open(stored_file.file) as stored_image:
        assert not dict(stored_image.getexif())


@pytest.mark.django_db
# A palette image grows when it is recompressed, which must not stop it from being
# scaled down to the maximum dimensions.
@pytest.mark.parametrize("mode", ["RGB", "P"])
def test_session_upload_caps_oversized_image(
    event, session_client, granted_upload_permission, settings, tmp_path, mode
):
    settings.MEDIA_ROOT = str(tmp_path)
    upload = png_upload(size=(settings.IMAGE_DEFAULT_MAX_WIDTH + 400, 100), mode=mode)

    response = upload_with_csrf_token(session_client, event, settings.CSRF_COOKIE_NAME, file=upload)

    assert response.status_code == 201
    with Image.open(StoredFile.objects.get().file) as stored_image:
        assert stored_image.width == settings.IMAGE_DEFAULT_MAX_WIDTH


@pytest.mark.django_db
def test_session_upload_names_unrecompressed_file_after_its_format(
    event, session_client, granted_upload_permission, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)

    response = upload_with_csrf_token(
        session_client, event, settings.CSRF_COOKIE_NAME, file=gif_upload(name="avatar.png")
    )

    assert response.status_code == 201
    stored_file = StoredFile.objects.get()
    assert stored_file.type == "image/gif"
    assert stored_file.filename == "avatar.gif"
    assert stored_file.file.name.endswith(".gif")
    with Image.open(stored_file.file) as stored_image:
        assert stored_image.is_animated
