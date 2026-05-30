"""Tests for speaker avatar download during CSV import."""
import datetime as dt
from unittest.mock import MagicMock, patch

import pytest
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, User
from eventyay.base.services.talkimport import (
    _normalize_avatar_url,
    _set_external_avatar_url,
    import_speaker_records,
)


@pytest.fixture
def _event():
    with scopes_disabled():
        from eventyay.base.models.organizer import Organizer, Team

        org = Organizer.objects.create(name='Test Org', slug='testorg')
        Team.objects.create(
            name='Organisers',
            organizer=org,
            can_create_events=True,
            can_change_teams=True,
            can_change_organizer_settings=True,
            can_change_event_settings=True,
            can_change_submissions=True,
        )
        today = dt.date.today()
        event = Event.objects.create(
            name='Avatar Import Test',
            is_public=True,
            slug='avatartest',
            email='test@test.org',
            date_from=today,
            date_to=today + dt.timedelta(days=1),
            organizer=org,
        )
    return event


# --- Unit tests for URL normalisation ---


@pytest.mark.parametrize(
    'input_url,expected',
    [
        ('https://example.com/photo.png', 'https://example.com/photo.png'),
        ('http://example.com/photo.jpg', 'http://example.com/photo.jpg'),
        ('//example.com/photo.png', 'https://example.com/photo.png'),
        ('', ''),
        ('not-a-url', ''),
        ('ftp://example.com/file', ''),
        ('  https://example.com/photo.png  ', 'https://example.com/photo.png'),
    ],
)
def test_normalize_avatar_url(input_url, expected):
    assert _normalize_avatar_url(input_url) == expected


# --- Helpers ---


def _make_mock_response(data: bytes) -> MagicMock:
    """Return a MagicMock that looks like a non-redirect streaming response."""
    resp = MagicMock()
    resp.is_redirect = False
    resp.raise_for_status = MagicMock()
    # iter_content must yield chunks; wrap in a list so it works for any chunk_size
    resp.iter_content.return_value = iter([data])
    return resp


# --- Unit tests for _set_external_avatar_url ---


@pytest.mark.django_db
def test_set_external_avatar_url_downloads_image():
    """When the URL is reachable, the image is downloaded and saved to user.avatar."""
    with scopes_disabled():
        user = User.objects.create_user(
            email='download@test.com',
            password='test',
            fullname='Download Test',
        )

    fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    mock_response = _make_mock_response(fake_png)

    with patch('eventyay.base.services.talkimport.requests.get', return_value=mock_response) as mock_get:
        fields = _set_external_avatar_url(user, 'https://example.com/avatars/test.png')

    mock_get.assert_called_once_with(
        'https://example.com/avatars/test.png',
        timeout=(5, 10),
        allow_redirects=False,
        stream=True,
    )
    assert 'avatar' in fields
    assert user.avatar
    assert user.avatar.name.startswith('avatars/')
    assert user.avatar.name.endswith('.png')


@pytest.mark.django_db
def test_set_external_avatar_url_fallback_on_download_failure():
    """When download fails, store the external URL in user.profile as fallback."""
    with scopes_disabled():
        user = User.objects.create_user(
            email='fallback@test.com',
            password='test',
            fullname='Fallback Test',
        )

    import requests as req

    with patch(
        'eventyay.base.services.talkimport.requests.get',
        side_effect=req.exceptions.ConnectionError('Connection refused'),
    ):
        fields = _set_external_avatar_url(user, 'https://dead-server.example.com/avatar.jpg')

    assert 'profile' in fields
    assert user.profile['avatar']['url'] == 'https://dead-server.example.com/avatar.jpg'
    assert not user.avatar


@pytest.mark.django_db
def test_set_external_avatar_url_skips_existing_avatar():
    """If user already has a local avatar, skip downloading."""
    from django.core.files.base import ContentFile

    with scopes_disabled():
        user = User.objects.create_user(
            email='existing@test.com',
            password='test',
            fullname='Existing Avatar',
        )
        user.avatar.save('existing.png', ContentFile(b'fake image'), save=True)

    with patch('eventyay.base.services.talkimport.requests.get') as mock_get:
        fields = _set_external_avatar_url(user, 'https://example.com/new-avatar.png')

    mock_get.assert_not_called()
    assert fields == []


@pytest.mark.parametrize('input_url', ['', 'not-a-url', 'ftp://example.com/img.png'])
def test_set_external_avatar_url_invalid_url_returns_empty(input_url):
    """Empty or invalid URLs return [] and never trigger a download."""
    with patch('eventyay.base.services.talkimport.requests.get') as mock_get:
        fields = _set_external_avatar_url(object(), input_url)
    assert fields == []
    mock_get.assert_not_called()


@pytest.mark.django_db
def test_set_external_avatar_url_handles_unknown_extension():
    """URLs without a recognisable image extension default to .jpg."""
    with scopes_disabled():
        user = User.objects.create_user(
            email='noext@test.com',
            password='test',
            fullname='No Extension',
        )

    fake_img = b'\xff\xd8\xff' + b'\x00' * 100
    mock_response = _make_mock_response(fake_img)

    with patch('eventyay.base.services.talkimport.requests.get', return_value=mock_response):
        fields = _set_external_avatar_url(user, 'https://example.com/api/avatar?id=123')

    assert 'avatar' in fields
    assert user.avatar.name.endswith('.jpg')


# --- Integration tests for import_speaker_records with avatar ---


@pytest.mark.django_db
def test_import_speaker_records_downloads_avatar(_event):
    """Full integration: import_speaker_records downloads avatar when avatar_url is provided."""
    fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    mock_response = _make_mock_response(fake_png)

    with scopes_disabled():
        acting_user = User.objects.create_user(
            email='orga@example.com', password='test', fullname='Organiser'
        )

    records = [
        {
            'email': 'speaker1@example.com',
            'full_name': 'Test Speaker',
            'avatar_url': 'https://example.com/photo.png',
        },
    ]

    with (
        patch('eventyay.base.services.talkimport.requests.get', return_value=mock_response),
        patch.object(User, 'process_image'),
    ):
        result = import_speaker_records(_event, records, acting_user)

    assert result['created'] == 1
    assert result['skipped'] == 0

    with scopes_disabled():
        user = User.objects.get(email='speaker1@example.com')
        assert user.avatar
        assert user.has_avatar


@pytest.mark.django_db
def test_import_speaker_records_fallback_avatar(_event):
    """When avatar download fails, external URL is stored in profile."""
    import requests as req

    with scopes_disabled():
        acting_user = User.objects.create_user(
            email='orga2@example.com', password='test', fullname='Organiser'
        )

    records = [
        {
            'email': 'speaker2@example.com',
            'full_name': 'Fallback Speaker',
            'avatar_url': 'https://dead-server.example.com/photo.png',
        },
    ]

    with patch(
        'eventyay.base.services.talkimport.requests.get',
        side_effect=req.exceptions.ConnectionError('timeout'),
    ):
        result = import_speaker_records(_event, records, acting_user)

    assert result['created'] == 1

    with scopes_disabled():
        user = User.objects.get(email='speaker2@example.com')
        assert not user.avatar
        assert user.has_avatar
        assert user.external_avatar_url == 'https://dead-server.example.com/photo.png'


@pytest.mark.django_db
def test_import_speaker_records_no_avatar(_event):
    """Speakers imported without avatar_url have no avatar."""
    with scopes_disabled():
        acting_user = User.objects.create_user(
            email='orga3@example.com', password='test', fullname='Organiser'
        )

    records = [
        {
            'email': 'speaker3@example.com',
            'full_name': 'No Avatar Speaker',
        },
    ]

    result = import_speaker_records(_event, records, acting_user)
    assert result['created'] == 1

    with scopes_disabled():
        user = User.objects.get(email='speaker3@example.com')
        assert not user.avatar
        assert not user.has_avatar


@pytest.mark.django_db
def test_import_speaker_records_process_image_called_after_save(_event):
    """process_image is called AFTER user.save, not before."""
    fake_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    mock_response = _make_mock_response(fake_png)

    with scopes_disabled():
        acting_user = User.objects.create_user(
            email='orga4@example.com', password='test', fullname='Organiser'
        )

    records = [
        {
            'email': 'speaker4@example.com',
            'full_name': 'Process Image Speaker',
            'avatar_url': 'https://example.com/photo.png',
        },
    ]

    with (
        patch('eventyay.base.services.talkimport.requests.get', return_value=mock_response),
        patch.object(User, 'process_image') as mock_process,
    ):
        import_speaker_records(_event, records, acting_user)

    mock_process.assert_called_once_with('avatar', generate_thumbnail=True)

    # Verify user was saved to DB with avatar field
    with scopes_disabled():
        user = User.objects.get(email='speaker4@example.com')
        assert user.avatar  # avatar path persisted in DB
