from eventyay.base.meetup import (
    VIDEO_TYPE_CHOICES,
    VIDEO_TYPE_HLS,
    VIDEO_TYPE_YOUTUBE,
    get_video_config_from_modules,
    get_video_module_config,
)


def test_meetup_video_type_choices():
    choice_keys = [k for k, _ in VIDEO_TYPE_CHOICES]
    assert choice_keys == ['', VIDEO_TYPE_YOUTUBE, VIDEO_TYPE_HLS]


def test_meetup_youtube_and_hls_streams_are_unchanged():
    youtube = get_video_module_config(VIDEO_TYPE_YOUTUBE, 'dQw4w9WgXcQ')
    assert youtube == [{'type': 'livestream.youtube', 'config': {'ytid': 'dQw4w9WgXcQ'}}]
    assert get_video_config_from_modules(youtube) == {
        'video_type': 'youtube',
        'video_url': 'dQw4w9WgXcQ',
    }

    hls = get_video_module_config(VIDEO_TYPE_HLS, 'https://example.com/live.m3u8')
    assert hls == [{'type': 'livestream.native', 'config': {'hls_url': 'https://example.com/live.m3u8'}}]
    assert get_video_config_from_modules(hls) == {
        'video_type': 'hls',
        'video_url': 'https://example.com/live.m3u8',
    }
