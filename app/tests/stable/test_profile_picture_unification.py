from unittest.mock import MagicMock

from eventyay.base.services.user import merge_video_profile, sync_video_profile_picture


def test_sync_video_profile_picture_uses_platform_account():
    video_user = MagicMock()
    video_user.profile = {
        'display_name': 'Demo User',
        'avatar': {'url': 'https://video.example/old.png'},
    }
    platform_user = MagicMock()
    platform_user.get_profile_picture_url.return_value = 'https://eventyay.example/profile.png'

    sync_video_profile_picture(video_user, platform_user=platform_user)

    assert video_user.profile == {
        'display_name': 'Demo User',
        'avatar': {'url': 'https://eventyay.example/profile.png'},
    }
    video_user.save.assert_called_once_with(update_fields=['profile'])


def test_sync_video_profile_picture_removes_legacy_avatar():
    video_user = MagicMock()
    video_user.profile = {
        'display_name': 'Demo User',
        'avatar': {'url': 'https://video.example/old.png'},
    }
    platform_user = MagicMock()
    platform_user.get_profile_picture_url.return_value = ''

    sync_video_profile_picture(video_user, platform_user=platform_user)

    assert video_user.profile == {'display_name': 'Demo User'}
    video_user.save.assert_called_once_with(update_fields=['profile'])


def test_merge_video_profile_keeps_server_avatar():
    current = {'avatar': {'url': 'https://eventyay.example/profile.png'}}
    incoming = {
        'display_name': 'Updated User',
        'avatar': {'url': 'https://video.example/replacement.png'},
    }

    assert merge_video_profile(current, incoming) == {
        'display_name': 'Updated User',
        'avatar': {'url': 'https://eventyay.example/profile.png'},
    }
