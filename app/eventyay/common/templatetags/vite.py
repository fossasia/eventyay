import logging
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

import msgspec
from django import template
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.safestring import mark_safe

register = template.Library()
logger = logging.getLogger(__name__)

# The vite_asset tag is only used for schedule-editor app, we only need find manifest.json file
# for this app.
MANIFEST_PATH = cast(Path, settings.STATIC_ROOT) / 'schedule-editor' / 'schedule-editor-manifest.json'


class ViteManifestEntry(msgspec.Struct):
    """Typed Vite manifest entry (mirrors Vite's manifest.json shape)."""

    file: str
    src: str | None = None
    name: str | None = None
    is_entry: bool = msgspec.field(default=False, name='isEntry')
    css: list[str] = msgspec.field(default_factory=list)
    assets: list[str] = msgspec.field(default_factory=list)
    imports: list[str] = msgspec.field(default_factory=list)
    dynamic_imports: list[str] = msgspec.field(default_factory=list, name='dynamicImports')
    integrity: str | None = None


ManifestMapping = dict[str, ViteManifestEntry]


def load_mapping() -> ManifestMapping:
    """Loads the Vite manifest file mapping using msgspec for fast decoding."""
    try:
        return msgspec.json.decode(MANIFEST_PATH.read_text(), type=ManifestMapping)
    except FileNotFoundError as e:
        raise ImproperlyConfigured(f'Vite manifest not found at {MANIFEST_PATH}.') from e
    except msgspec.ValidationError as e:
        raise ImproperlyConfigured(f'Vite manifest at {MANIFEST_PATH} has an unexpected format.') from e


def generate_script_tag(path: str, attrs: dict[str, str]) -> str:
    all_attrs = ' '.join(f'{key}="{value}"' for key, value in attrs.items())
    if settings.VITE_DEV_MODE:
        src = urljoin(settings.VITE_DEV_SERVER, path)
    else:
        src = urljoin(settings.STATIC_URL, f'schedule-editor/{path}')
    return f'<script {all_attrs} src="{src}"></script>'


def generate_css_tags(asset: str, already_processed: list[str], static_files_mapping: ManifestMapping) -> list[str]:
    """Recursively builds all CSS tags used in a given asset.

    Ignore the side effects."""
    tags = []
    manifest_entry = static_files_mapping[asset]

    # Put our own CSS file first for specificity
    if manifest_entry.css:
        for css_path in manifest_entry.css:
            if css_path not in already_processed:
                full_path = urljoin(settings.STATIC_URL, f'schedule-editor/{css_path}')
                tags.append(f'<link rel="stylesheet" href="{full_path}" />')
            already_processed.append(css_path)

    # Import each file only one by way of side effects in already_processed
    if manifest_entry.imports:
        for import_path in manifest_entry.imports:
            tags += generate_css_tags(import_path, already_processed, static_files_mapping)

    return tags


@register.simple_tag
@mark_safe
def vite_asset(path: str) -> str:
    """
    Generates one <script> tag and <link> tags for each of the CSS dependencies.

    Only applied for schedule-editor related assets.
    """

    if not path:
        return ''

    static_files_mapping = load_mapping()

    if settings.VITE_DEV_MODE:
        return generate_script_tag(path, {'type': 'module'})

    manifest_entry = static_files_mapping.get(path)
    if manifest_entry is None:
        msg = (
            f'Cannot find {path} in Vite manifest at {MANIFEST_PATH}.'
            if MANIFEST_PATH.exists()
            else f'Vite manifest {MANIFEST_PATH} not found.'
        )
        raise ImproperlyConfigured(msg)

    tags = generate_css_tags(path, [], static_files_mapping)
    tags.append(generate_script_tag(manifest_entry.file, {'type': 'module', 'crossorigin': ''}))
    return ''.join(tags)


@register.simple_tag
@mark_safe
def vite_hmr() -> str:
    if not settings.VITE_DEV_MODE:
        return ''
    return generate_script_tag('@vite/client', {'type': 'module'})
