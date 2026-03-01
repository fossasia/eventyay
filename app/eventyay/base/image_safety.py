import logging
from typing import IO

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError


logger = logging.getLogger(__name__)


# Max 25 Megapixels allows for high-resolution images (up to ~5000x5000 pixels)
# while preventing server memory exhaustion (DoS attacks)
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_FORMATS = ('JPEG', 'PNG', 'GIF', 'BMP', 'TIFF')


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
    try:
        # Ensure we are at the start of the file if it's a file object
        if not isinstance(file_obj, str):
            file_obj.seek(0)

        # Open in lazy mode (does not read pixel data yet)
        with Image.open(file_obj, formats=ALLOWED_FORMATS) as img:
            # Verify the full image header so size is reliably populated
            img.verify()

            # Explicit dimension check against decomp bombs
            width, height = img.size
            if width * height > MAX_IMAGE_PIXELS:
                logger.warning('Image rejected: Too large (%dx%d)', width, height)
                raise ValidationError(
                    _('Image is too large. Maximum resolution is {max_pixels} pixels.')
                    .format(max_pixels=f'{MAX_IMAGE_PIXELS:,}')
                )

        # Reset file pointer for the next consumer (e.g. reportlab)
        if not isinstance(file_obj, str):
            file_obj.seek(0)

    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError):
        # Catch explicit exceptions from Pillow like UnidentifiedImageError or OSError
        logger.warning('Error validating image')
        raise ValidationError(_('Invalid or corrupted image file.'))
