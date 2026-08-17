from django.core.files.uploadedfile import SimpleUploadedFile
from django_scopes import scopes_disabled
import pytest

from eventyay.base.models import Event, Organizer, Poster, Room
from eventyay.base.models.poster import (
    poster_file_path,
    poster_preview_file_path,
)


@pytest.fixture
def poster_setup():
    with scopes_disabled():
        org = Organizer.objects.create(name="Poster Org", slug="posterorg")
        event = Event.objects.create(
            organizer=org,
            name="Poster Event",
            slug="posterevent",
            currency="EUR",
        )
        room = Room.objects.create(
            event=event,
            name="Poster Hall",
        )
    return event, room


@pytest.mark.django_db
def test_poster_paths(poster_setup):
    event, room = poster_setup
    with scopes_disabled():
        poster = Poster.objects.create(
            event=event,
            parent_room=room,
            title="Sample Research Poster",
        )

        file_path = poster_file_path(poster, "test_poster.pdf")
        assert f"events/{event.slug}/posters/" in file_path
        assert file_path.endswith(".pdf")

        preview_path = poster_preview_file_path(poster, "test_preview.png")
        assert f"events/{event.slug}/posters/previews/" in preview_path
        assert preview_path.endswith(".png")


@pytest.mark.django_db
def test_poster_fallback_url_when_no_file(poster_setup):
    event, room = poster_setup
    with scopes_disabled():
        poster = Poster.objects.create(
            event=event,
            parent_room=room,
            title="External URL Poster",
            poster_url="https://example.com/poster.pdf",
            poster_preview="https://example.com/preview.png",
        )

        assert poster.resolved_poster_url == "https://example.com/poster.pdf"
        assert poster.resolved_poster_preview == "https://example.com/preview.png"

        serialized = poster.serialize()
        assert serialized["poster_url"] == "https://example.com/poster.pdf"
        assert serialized["poster_preview"] == "https://example.com/preview.png"


@pytest.mark.django_db
def test_poster_file_upload_resolution_and_serialization(poster_setup):
    event, room = poster_setup
    with scopes_disabled():
        fake_pdf = SimpleUploadedFile("research.pdf", b"%PDF-1.4 test poster content", content_type="application/pdf")
        fake_preview = SimpleUploadedFile("preview.png", b"\x89PNG\r\n\x1a\n test png", content_type="image/png")

        poster = Poster.objects.create(
            event=event,
            parent_room=room,
            title="Uploaded Research Poster",
            poster_file=fake_pdf,
            poster_preview_file=fake_preview,
        )

        assert poster.poster_file.name is not None
        assert poster.poster_preview_file.name is not None
        assert poster.resolved_poster_url == poster.poster_file.url
        assert poster.resolved_poster_preview == poster.poster_preview_file.url

        serialized = poster.serialize()
        assert serialized["poster_url"] == poster.poster_file.url
        assert serialized["poster_preview"] == poster.poster_preview_file.url

        # Clean up files on deletion
        poster_file_name = poster.poster_file.name
        poster.delete()
        assert not poster.poster_file.storage.exists(poster_file_name)
