"""
Image optimization helpers for event logo and header image uploads.

Uploaded images are resized to a maximum width on save so that public pages
never serve the original, potentially multi-megabyte file.  The original is
always preserved alongside the optimized version so that organisers can
re-crop or reprocess it in a future release.

Usage::

    from eventyay.helpers.image_optimize import optimize_uploaded_image

    result = optimize_uploaded_image(
        uploaded_file,
        setting_key='logo_image',   # 'logo_image' or 'event_logo_image'
    )
    # Save `result.optimized` to storage; `result.original` can be stored at a sibling path.
"""

from __future__ import annotations

import logging
import os
from io import BytesIO
from typing import NamedTuple

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps
from PIL.Image import Resampling

logger = logging.getLogger(__name__)

# Maximum output width per asset type.  Height is always proportional.
MAX_WIDTH: dict[str, int] = {
    'logo_image': 3000,       # header/banner image
    'event_logo_image': 1000, # event logo
    'og_image': 1200,         # social media preview image
}

JPEG_QUALITY = 85


class OptimizedImages(NamedTuple):
    """Pair of ContentFile objects returned by optimize_uploaded_image."""

    optimized: ContentFile
    """The resized/recompressed file that should be stored and served."""

    original: ContentFile
    """The untouched original bytes, stored for future re-processing."""

    optimized_ext: str
    """File extension (without leading dot) for the optimized file."""

    original_ext: str
    """File extension (without leading dot) for the original file."""


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ('RGBA', 'LA', 'PA') or (
        image.mode == 'P' and 'transparency' in image.info
    )


def _encode_optimized(image: Image.Image) -> tuple[bytes, str]:
    """
    Encode *image* as progressive JPEG or PNG (for images with alpha).

    Returns ``(data_bytes, extension)`` where *extension* is ``'jpg'`` or
    ``'png'``.
    """
    buf = BytesIO()
    if _has_alpha(image):
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        image.save(buf, format='PNG', optimize=True)
        return buf.getvalue(), 'png'
    else:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buf, format='JPEG', quality=JPEG_QUALITY, progressive=True, optimize=True)
        return buf.getvalue(), 'jpg'


def optimize_uploaded_image(
    uploaded: UploadedFile,
    setting_key: str,
    crop_box: tuple[int, int, int, int] | None = None,
) -> OptimizedImages:
    """
    Resize *uploaded* to the cap for *setting_key* and return both the
    optimized and the original as ``ContentFile`` objects.

    If the image is already within the maximum width it is still re-encoded
    to ensure consistent output format, but its dimensions are not changed.

    Raises ``ValueError`` for unknown *setting_key* values.
    Raises ``OSError`` / ``PIL.UnidentifiedImageError`` when the file cannot
    be decoded as an image.
    """
    if setting_key not in MAX_WIDTH:
        raise ValueError('Unknown image setting key: %s' % setting_key)

    max_w = MAX_WIDTH[setting_key]

    raw = uploaded.read()
    uploaded.seek(0)

    _, original_ext = os.path.splitext(uploaded.name or 'upload')
    original_ext = (original_ext.lstrip('.') or 'jpg').lower()

    image = Image.open(BytesIO(raw))
    try:
        image.load()
    except OSError:
        logger.exception('Could not load uploaded image for optimization')
        raise

    is_animated = getattr(image, 'is_animated', False)
    if is_animated:
        ext = image.format.lower() if image.format else original_ext
        logger.info('Bypassing optimization for animated %s image', ext)
        return OptimizedImages(
            optimized=ContentFile(raw),
            original=ContentFile(raw),
            optimized_ext=ext,
            original_ext=original_ext,
        )

    image = ImageOps.exif_transpose(image)

    if crop_box:
        logger.info('Cropping %s to %s', setting_key, crop_box)
        image = image.crop(crop_box)

    orig_w, orig_h = image.size
    if orig_w > max_w:
        scale_factor = max_w / orig_w
        new_w = max_w
        new_h = max(1, int(orig_h * scale_factor))
        image = image.resize((new_w, new_h), resample=Resampling.LANCZOS)
        logger.info(
            'Resized %s from %dx%d to %dx%d',
            setting_key,
            orig_w,
            orig_h,
            new_w,
            new_h,
        )

    optimized_bytes, optimized_ext = _encode_optimized(image)
    optimized_file = ContentFile(optimized_bytes)
    original_file = ContentFile(raw)

    return OptimizedImages(
        optimized=optimized_file,
        original=original_file,
        optimized_ext=optimized_ext,
        original_ext=original_ext,
    )
