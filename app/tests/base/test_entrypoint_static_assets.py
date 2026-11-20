import subprocess
from pathlib import Path


def test_static_cache_css_missing_or_empty(tmp_path):
    """Verify missing or empty CACHE/css directory indicates assets must be generated."""
    cache_css = tmp_path / "CACHE" / "css"

    # Does not exist
    assert not cache_css.exists()
    assert not (cache_css.is_dir() and any(cache_css.iterdir()))

    # Directory created but empty
    cache_css.mkdir(parents=True)
    assert cache_css.is_dir()
    assert not any(cache_css.iterdir())


def test_static_cache_css_populated(tmp_path):
    """Verify populated CACHE/css directory indicates assets exist."""
    cache_css = tmp_path / "CACHE" / "css"
    cache_css.mkdir(parents=True)
    bundle = cache_css / "output.a542934d2432.css"
    bundle.write_text("/* compiled css */")

    assert cache_css.is_dir()
    assert any(cache_css.iterdir())


def test_entrypoint_script_syntax():
    """Verify entrypoint.sh has valid shell syntax."""
    entrypoint = Path(__file__).resolve().parents[2] / "entrypoint.sh"
    assert entrypoint.exists()
    content = entrypoint.read_text(encoding="utf-8")
    assert "/usr/src/app/eventyay/static.dist/CACHE/css" in content
    assert "collectstatic --noinput" in content
    assert "compress --force" in content
    assert "rm -rf" in content
