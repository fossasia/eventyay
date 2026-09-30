from django.test import RequestFactory

from eventyay.multidomain.views import (
    VIDEO_ASSET_CACHE,
    VideoAssetView,
    video_asset_cache_control,
)


def test_video_assets_cache_for_one_hour():
    assert video_asset_cache_control('assets/main.js') == VIDEO_ASSET_CACHE
    assert video_asset_cache_control('assets/vendor-hls.css') == VIDEO_ASSET_CACHE
    assert video_asset_cache_control(r'assets\font.woff2') == VIDEO_ASSET_CACHE
    assert video_asset_cache_control('preloader.js') == VIDEO_ASSET_CACHE
    assert video_asset_cache_control('sw.js') == VIDEO_ASSET_CACHE
    assert video_asset_cache_control('manifest.webmanifest') == VIDEO_ASSET_CACHE


def test_video_asset_view_sets_cache_header(tmp_path, monkeypatch, settings):
    settings.VITE_DEV_MODE = False
    asset_dir = tmp_path / 'assets'
    asset_dir.mkdir()
    (asset_dir / 'main.js').write_text('console.log(1)\n', encoding='utf-8')
    (tmp_path / 'preloader.js').write_text('console.log(2)\n', encoding='utf-8')
    monkeypatch.setattr('eventyay.multidomain.views.VIDEO_DIST_DIR', tmp_path)

    asset = VideoAssetView.as_view()(
        RequestFactory().get('/org/event/video/assets/main.js'),
        path='assets/main.js',
    )
    assert asset.status_code == 200
    assert asset['Cache-Control'] == VIDEO_ASSET_CACHE

    root = VideoAssetView.as_view()(
        RequestFactory().get('/org/event/video/preloader.js'),
        path='preloader.js',
    )
    assert root.status_code == 200
    assert root['Cache-Control'] == VIDEO_ASSET_CACHE
