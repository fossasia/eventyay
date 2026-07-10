import logging
import os
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.utils._os import safe_join
from django.utils.crypto import get_random_string

from eventyay.common.urls import get_file_url_path, is_http_url

logger = logging.getLogger(__name__)


def path_with_hash(name, base_path=None, max_length=100):
    base_path = base_path or ''
    dir_name, file_name = os.path.split(name)
    file_root, file_ext = os.path.splitext(file_name)
    file_root = safe_filename(file_root)
    random = get_random_string(7)
    if base_path and max_length:
        # We need to resolve the base path for its actual total length, as absolute
        # paths are stored in the database.
        full_base_path = Path(settings.MEDIA_ROOT) / base_path
        total_length = len(str(full_base_path / dir_name / f'{file_root}_{random}{file_ext}'))
        if total_length > max_length:
            # If the total length of the path exceeds the max length, we need to
            # shorten the file name by the difference.
            file_root = file_root[: -(total_length - max_length)]
    return str(Path(base_path) / dir_name / f'{file_root}_{random}{file_ext}')


def safe_filename(filename):
    return unicodedata.normalize('NFD', filename).encode('ASCII', 'ignore').decode()


def resolve_media_path(obj):
    """
    Convert an arbitrary image setting value (string, dict, or file-like) to a
    storage-relative path suitable for passing to ``default_storage.url()`` or
    ``get_thumbnail()``.  Returns an absolute HTTP/HTTPS URL unchanged, and
    returns ``None`` when the value is empty or unsafe.

    Path traversal protection: after resolving the raw value to an absolute
    filesystem path, ``safe_join`` is used to verify the path is contained
    within ``MEDIA_ROOT``.  Any path that escapes (e.g. ``../../secret``) is
    logged and rejected, returning ``None``.
    """
    # Step 1: extract a raw string from whatever the setting stores.
    if not obj:
        return None
    if isinstance(obj, dict):
        path = obj.get('name') or obj.get('path') or obj.get('url')
    elif hasattr(obj, 'name') and obj.name:
        path = obj.name
    elif hasattr(obj, 'url'):
        path = obj.url
    else:
        path = str(obj)

    if not path:
        return None

    # Step 2: pass through absolute HTTP(S) URLs untouched.
    if is_http_url(path):
        return path

    # Step 3: strip a file:// scheme if present.
    # get_file_url_path() handles both file://pub/... (netloc='pub') and
    # any other file:// variant consistently via urlsplit.
    file_path = get_file_url_path(path)
    if file_path is not None:
        path = file_path

    # Step 4: strip legacy /media/ prefix before resolving.
    for prefix in ('/media/', 'media/'):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break

    # Step 5: resolve to an absolute path and verify containment in MEDIA_ROOT
    #         using Django's safe_join, which raises SuspiciousFileOperation for
    #         any path that would escape the root (e.g. containing '..' segments).
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    try:
        abs_candidate = safe_join(media_root, path)
    except SuspiciousFileOperation:
        logger.warning(
            'Rejected image path %r: it would escape MEDIA_ROOT (%s)',
            path,
            media_root,
        )
        return None

    # Step 6: return a storage-relative path (no leading slash).
    return os.path.relpath(abs_candidate, media_root)
