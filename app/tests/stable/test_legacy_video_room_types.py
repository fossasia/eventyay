from eventyay.base.meetup import (
    VIDEO_TYPE_HLS,
    VIDEO_TYPE_IFRAME,
    VIDEO_TYPE_YOUTUBE,
    get_video_config_from_modules,
    get_video_module_config,
)


def test_meetup_iframe_uses_stage_livestream_module():
    modules = get_video_module_config(VIDEO_TYPE_IFRAME, 'https://example.com/embed')
    assert modules == [
        {'type': 'livestream.iframe', 'config': {'url': 'https://example.com/embed'}}
    ]
    assert get_video_config_from_modules(modules) == {
        'video_type': 'iframe',
        'video_url': 'https://example.com/embed',
    }


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
