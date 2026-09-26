from django.test import RequestFactory

from eventyay.multidomain.views import (
    IMMUTABLE_VIDEO_ASSET_CACHE,
    SHORT_VIDEO_ASSET_CACHE,
    VideoAssetView,
    video_asset_cache_control,
)


def test_hashed_video_assets_are_immutable():
    assert video_asset_cache_control('assets/main-AbCdEf12.js') == IMMUTABLE_VIDEO_ASSET_CACHE
    assert video_asset_cache_control('assets/vendor-hls-Dk19aBcE.css') == IMMUTABLE_VIDEO_ASSET_CACHE
    assert video_asset_cache_control(r'assets\font-AbCdEf12.woff2') == IMMUTABLE_VIDEO_ASSET_CACHE


def test_unhashed_video_files_use_a_short_cache():
    assert video_asset_cache_control('preloader.js') == SHORT_VIDEO_ASSET_CACHE
    assert video_asset_cache_control('sw.js') == SHORT_VIDEO_ASSET_CACHE
    assert video_asset_cache_control('manifest.webmanifest') == SHORT_VIDEO_ASSET_CACHE
    assert video_asset_cache_control('assets/legacy.js') == SHORT_VIDEO_ASSET_CACHE


def test_video_asset_view_sets_cache_header(tmp_path, monkeypatch, settings):
    settings.VITE_DEV_MODE = False
    asset_dir = tmp_path / 'assets'
    asset_dir.mkdir()
    (asset_dir / 'main-AbCdEf12.js').write_text('console.log(1)\n', encoding='utf-8')
    (tmp_path / 'preloader.js').write_text('console.log(2)\n', encoding='utf-8')
    monkeypatch.setattr('eventyay.multidomain.views.VIDEO_DIST_DIR', tmp_path)

    hashed = VideoAssetView.as_view()(
        RequestFactory().get('/org/event/video/assets/main-AbCdEf12.js'),
        path='assets/main-AbCdEf12.js',
    )
    assert hashed.status_code == 200
    assert hashed['Cache-Control'] == IMMUTABLE_VIDEO_ASSET_CACHE

    root = VideoAssetView.as_view()(
        RequestFactory().get('/org/event/video/preloader.js'),
        path='preloader.js',
    )
    assert root.status_code == 200
    assert root['Cache-Control'] == SHORT_VIDEO_ASSET_CACHE
