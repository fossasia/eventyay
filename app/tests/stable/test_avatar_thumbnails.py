from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test.utils import override_settings

from eventyay.base.models.auth import User, list_avatar_urls, needs_avatar_thumbnails
from eventyay.person.tasks import (
    enqueue_missing_avatar_thumbnails,
    ensure_avatar_thumbnails,
)


LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'avatar-thumbnail-enqueue-tests',
    }
}


def _user_with_avatar(*, tiny_name=''):
    user = User()
    avatar = MagicMock()
    avatar.name = 'avatars/ab/speaker.jpg'
    avatar.field = SimpleNamespace(name='avatar')
    user.avatar = avatar
    tiny = MagicMock()
    tiny.name = tiny_name
    user.avatar_thumbnail_tiny = tiny
    return user


def test_get_avatar_url_skips_original_when_thumbnail_missing():
    user = _user_with_avatar()
    assert user.get_avatar_url(thumbnail='tiny', generate_missing=False) == ''


def test_get_avatar_url_uses_stored_tiny_thumbnail():
    user = _user_with_avatar(tiny_name='avatars/ab/speaker_thumbnail_tiny.jpg')
    user.avatar_thumbnail_tiny.url = '/media/avatars/ab/speaker_thumbnail_tiny.jpg'
    url = user.get_avatar_url(thumbnail='tiny', generate_missing=False)
    assert 'speaker_thumbnail_tiny.jpg' in url


def test_list_avatar_urls_skips_generation_and_marks_missing_thumbs():
    user = _user_with_avatar()
    urls = list_avatar_urls(user)
    assert urls['avatar_thumbnail_tiny'] is None
    assert needs_avatar_thumbnails(user, urls)
    assert list_avatar_urls(user, include=False) == {
        'avatar': None,
        'avatar_thumbnail_default': None,
        'avatar_thumbnail_tiny': None,
    }


@override_settings(CACHES=LOCMEM_CACHE)
def test_enqueue_missing_avatar_thumbnails_rate_limits():
    cache.clear()
    with patch('eventyay.person.tasks.ensure_avatar_thumbnails.delay') as delay:
        enqueue_missing_avatar_thumbnails(12, [1, 2, 3])
        enqueue_missing_avatar_thumbnails(12, [4, 5])
        delay.assert_called_once_with([1, 2, 3])


def test_needs_avatar_thumbnails_requires_both_sizes():
    user = _user_with_avatar(tiny_name='avatars/ab/speaker_thumbnail_tiny.jpg')
    assert needs_avatar_thumbnails(
        user,
        {'avatar_thumbnail_tiny': '/tiny.jpg', 'avatar_thumbnail_default': None},
    )
    assert not needs_avatar_thumbnails(
        user,
        {'avatar_thumbnail_tiny': '/tiny.jpg', 'avatar_thumbnail_default': '/default.jpg'},
    )


@override_settings(CACHES=LOCMEM_CACHE)
def test_enqueue_missing_avatar_thumbnails_dispatches_all_batches():
    cache.clear()
    ids = list(range(1, 402))
    with patch('eventyay.person.tasks.ensure_avatar_thumbnails.delay') as delay:
        enqueue_missing_avatar_thumbnails(12, ids)
        assert delay.call_count == 3
        assert delay.call_args_list[0].args[0] == list(range(1, 201))
        assert delay.call_args_list[1].args[0] == list(range(201, 401))
        assert delay.call_args_list[2].args[0] == [401]


@override_settings(CACHES=LOCMEM_CACHE)
def test_enqueue_missing_avatar_thumbnails_skips_empty():
    cache.clear()
    with patch('eventyay.person.tasks.ensure_avatar_thumbnails.delay') as delay:
        enqueue_missing_avatar_thumbnails(12, [])
        delay.assert_not_called()


def test_ensure_avatar_thumbnails_creates_missing_sizes():
    user = SimpleNamespace(
        avatar=SimpleNamespace(name='avatars/ab/speaker.jpg', field=SimpleNamespace(name='avatar')),
        avatar_thumbnail_tiny=SimpleNamespace(name=''),
        avatar_thumbnail=SimpleNamespace(name='avatars/ab/speaker_thumbnail_default.jpg'),
    )

    with (
        patch('eventyay.person.tasks.User.objects.filter', return_value=[user]),
        patch('eventyay.person.tasks.create_thumbnail', return_value=MagicMock()) as create,
        patch('eventyay.person.tasks.SpeakerProfile.objects.filter') as profiles,
        patch('eventyay.person.tasks.bump_schedule_cache_version_on_commit') as bump,
    ):
        profiles.return_value.values_list.return_value.distinct.return_value = [9]
        ensure_avatar_thumbnails([1, 1])
        create.assert_called_once_with(user.avatar, 'tiny')
        bump.assert_called_once_with(9)
