import logging
import os
from typing import IO

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError


logger = logging.getLogger(__name__)


# Max 25 Megapixels allows for high-resolution images (up to ~5000x5000 pixels)
# while preventing server memory exhaustion (DoS attacks)
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_FORMATS = ('JPEG', 'PNG', 'GIF', 'BMP', 'TIFF')

# Apply a safe global upper bound once without loosening any stricter preconfigured
# limit. This avoids per-call global mutation races in concurrent requests.
if Image.MAX_IMAGE_PIXELS is None or Image.MAX_IMAGE_PIXELS > MAX_IMAGE_PIXELS:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def validate_image(file_obj: IO[bytes] | str) -> None:
    """
    Validates an image file's dimensions and format without loading
    the full pixel data into memory.

    Args:
        file_obj: A file-like object (e.g. Django UploadedFile or BytesIO)
            or a string path to an image file.

    Returns:
        None: Returns nothing if safe, raises ValidationError otherwise.
    """
    # For file-like objects, verify seekability upfront to ensure safe validation
    if not isinstance(file_obj, (str, os.PathLike)):
        try:
            file_obj.seek(0)
        except (AttributeError, OSError, ValueError) as e:
            logger.warning('File object is not seekable: %s', e, exc_info=True)
            raise ValidationError(
                _('Invalid file object: must be seekable or a file path.')
            )

    def rewind_file() -> None:
        """Reset file object to start for next consumer."""
        if isinstance(file_obj, str):
            return
        try:
            file_obj.seek(0)
        except (OSError, ValueError):
            # Should not happen since we validated seekability upfront
            logger.warning('Failed to reset file pointer', exc_info=True)

    try:
        # Ensure we are at the start of the file if it's a file object
        rewind_file()

        # Open in lazy mode (does not read pixel data yet)
        with Image.open(file_obj, formats=ALLOWED_FORMATS) as img:
            # Read dimensions from the header before verify() makes the
            # image object unusable (per Pillow documentation).
            width, height = img.size

            # Short-circuit oversized images before verify() does more work.
            if width * height > MAX_IMAGE_PIXELS:
                logger.warning('Image rejected: Too large (%dx%d)', width, height)
                raise ValidationError(
                    _('Image is too large. Maximum resolution is %(max_pixels)s pixels.')
                    % {'max_pixels': f'{MAX_IMAGE_PIXELS:,}'}
                )

            # Verify the full image header integrity
            img.verify()

        # Reset file pointer for the next consumer (e.g. reportlab)
        rewind_file()

    except ValidationError:
        raise
    except DecompressionBombError:
        logger.warning('Image rejected due to decompression bomb', exc_info=True)
        raise ValidationError(
            _('Image is too large or complex to be processed safely.')
        )
    except FileNotFoundError:
        logger.warning('Image file not found during validation', exc_info=True)
        raise ValidationError(_('Image file could not be found or read.'))
    except (SyntaxError, UnidentifiedImageError, OSError):
        # Catch explicit decode/parse failures from Pillow
        logger.warning('Error validating image', exc_info=True)
        raise ValidationError(_('Invalid or corrupted image file.'))
