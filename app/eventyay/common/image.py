import logging
import re
from functools import partial
from io import BytesIO
from pathlib import Path

from csp.decorators import csp_update
from defusedxml import ElementTree as DefusedElementTree
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps
from PIL.Image import MAX_IMAGE_PIXELS, DecompressionBombError, Resampling

from eventyay.common.templatetags.filesize import filesize

logger = logging.getLogger(__name__)

THUMBNAIL_SIZES = {
    'tiny': (64, 64),
    'default': (460, 460),
}

IMAGE_EXTENSIONS = {
    '.png': ['image/png', '.png'],
    '.jpg': ['image/jpeg', '.jpg'],
    '.jpeg': ['image/jpeg', '.jpeg'],
    '.gif': ['image/gif', '.gif'],
    '.svg': ['image/svg+xml', '.svg'],
    '.webp': ['image/webp', '.webp'],
}

ALLOWED_IMAGE_EXTENSIONS = frozenset(IMAGE_EXTENSIONS)

RASTER_THUMBNAIL_FORMATS = ('PNG', 'JPEG', 'GIF', 'WEBP')

FORBIDDEN_SVG_TAGS = frozenset(
    {
        'script',
        'foreignobject',
        'iframe',
        'embed',
        'object',
        'audio',
        'video',
    }
)

AVATAR_THUMBNAIL_FIELDS = ('avatar_thumbnail', 'avatar_thumbnail_tiny')


def thumbnail_matches_avatar(avatar_name, thumbnail_name, size):
    if not avatar_name or not thumbnail_name or size not in THUMBNAIL_SIZES:
        return False
    if str(avatar_name).lower().endswith('.svg'):
        return False
    avatar_path = Path(avatar_name)
    thumbnail_path = Path(thumbnail_name)
    return (
        thumbnail_path.stem == f'{avatar_path.stem}_thumbnail_{size}'
        and thumbnail_path.suffix == avatar_path.suffix
    )


def clear_avatar_thumbnails(instance):
    """Delete raster thumbnail files when the main avatar is replaced or removed."""
    for field_name in AVATAR_THUMBNAIL_FIELDS:
        thumbnail = getattr(instance, field_name, None)
        if thumbnail:
            thumbnail.delete(save=False)
        setattr(instance, field_name, None)


def invalidate_speaker_avatar_caches(user):
    """Drop cached speaker schedule JSON after avatar URLs may have changed."""
    if not user.code:
        return

    from eventyay.agenda.views.utils import clear_schedule_caches
    from eventyay.base.models import Event
    from eventyay.base.models.profile import SpeakerProfile

    event_ids = SpeakerProfile.objects.filter(user_id=user.pk).values_list('event_id', flat=True)
    for event in Event.objects.filter(pk__in=event_ids):
        clear_schedule_caches(event, speaker=user)

gravatar_csp = partial(
    csp_update,
    {
        'IMG_SRC': 'https://www.gravatar.com',
        'CONNECT_SRC': 'https://www.gravatar.com',
    },
)


def is_svg_filename(filename):
    return str(filename).lower().endswith('.svg')


def _read_uploaded_file(f):
    if hasattr(f, 'temporary_file_path'):
        with open(f.temporary_file_path(), 'rb') as uploaded:
            return uploaded.read()
    if hasattr(f, 'read'):
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        content = f.read()
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        return content
    return f['content']


def _svg_local_tag(tag):
    return tag.rsplit('}', 1)[-1].lower()


def _validate_svg_content(content):
    max_size = getattr(settings, 'IMAGE_SVG_MAX_SIZE', 1024 * 1024)
    if len(content) > max_size:
        raise ValidationError(
            _('SVG files must be smaller than {size}. Please simplify the image or upload a PNG/JPEG instead.').format(
                size=filesize(max_size),
            )
        )

    lowered = content.lower()
    if b'<script' in lowered or b'javascript:' in lowered:
        raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))

    try:
        root = DefusedElementTree.fromstring(content)
    except DefusedElementTree.ParseError as exc:
        raise ValidationError(
            _('Upload a valid SVG image. The file you uploaded was either not an SVG or a corrupted SVG.')
        ) from exc

    if _svg_local_tag(root.tag) != 'svg':
        raise ValidationError(
            _('Upload a valid SVG image. The file you uploaded was either not an SVG or a corrupted SVG.')
        )

    for element in root.iter():
        if _svg_local_tag(element.tag) in FORBIDDEN_SVG_TAGS:
            raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))
        for attr_name, attr_value in element.attrib.items():
            attr_name_lower = attr_name.lower()
            if attr_name_lower.startswith('on'):
                raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))
            if attr_name_lower in {'href', 'xlink:href'} and re.match(
                r'^\s*javascript:', attr_value, flags=re.IGNORECASE
            ):
                raise ValidationError(_('This SVG file contains disallowed content and cannot be uploaded.'))


def validate_image(f):
    if f is None:
        return None

    filename = getattr(f, 'name', '')
    if is_svg_filename(filename):
        _validate_svg_content(_read_uploaded_file(f))
        return

    if hasattr(f, 'temporary_file_path'):
        file = f.temporary_file_path()
    elif hasattr(f, 'read'):
        if hasattr(f, 'seek') and callable(f.seek):
            f.seek(0)
        file = BytesIO(f.read())
    else:
        file = BytesIO(f['content'])

    try:
        try:
            formats = getattr(settings, 'PILLOW_FORMATS_QUESTIONS_IMAGE', None) or RASTER_THUMBNAIL_FORMATS
            image = Image.open(file, formats=formats)
            # verify() must be called immediately after the constructor.
            image.verify()
        except DecompressionBombError:
            raise ValidationError(
                _(
                    'The file you uploaded has a very large number of pixels, please upload a picture with '
                    'smaller dimensions.'
                )
            )

        # load() is a potential DoS vector (see Django bug #18520), so we verify the size first
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValidationError(
                _(
                    'The file you uploaded has a very large number of pixels, please upload a picture with '
                    'smaller dimensions.'
                )
            )
    except Exception as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(
            _('Upload a valid image. The file you uploaded was either not an image or a corrupted image.')
        ) from exc
    if hasattr(f, 'seek') and callable(f.seek):
        f.seek(0)


def process_image(*, image, generate_thumbnail=False):
    """
    This function receives an image that has been uploaded, and processes it
    by reducing its file size and stripping its metadata.
    Image must be an ImageFieldFile, e.g. user.avatar.
    """
    if is_svg_filename(image.name):
        return

    try:
        img = Image.open(image)
    except Exception:
        logger.exception("Failed to process image")
        return

    if getattr(img, 'is_animated', False):
        if generate_thumbnail:
            for size in THUMBNAIL_SIZES:
                create_thumbnail(image, size)
        return

    extension = '.jpg'
    if img.mode.lower() in ('rgba', 'la', 'pa'):
        extension = '.png'
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    img_without_exif = Image.new(img.mode, img.size)
    img_without_exif.putdata(img.getdata())
    max_dimensions = (
        settings.IMAGE_DEFAULT_MAX_WIDTH,
        settings.IMAGE_DEFAULT_MAX_HEIGHT,
    )
    img_without_exif = ImageOps.exif_transpose(img_without_exif)
    img_without_exif.thumbnail(max_dimensions, resample=Resampling.LANCZOS)

    # Overwrite the original image with the processed one
    img_without_exif.save(image.path, quality='web_high' if extension == '.jpg' else 95)

    if generate_thumbnail:
        for size in THUMBNAIL_SIZES:
            create_thumbnail(image, size)


def get_thumbnail_field_name(image, size):
    thumbnail_field_name = f'{image.field.name}_thumbnail'
    if size != 'default':
        thumbnail_field_name += f'_{size}'
    return thumbnail_field_name


def create_thumbnail(image, size):
    if size not in THUMBNAIL_SIZES:
        return
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not image.instance._meta.get_field(thumbnail_field_name):
        return

    if is_svg_filename(image.name):
        return None

    try:
        img = Image.open(image, formats=RASTER_THUMBNAIL_FORMATS)
        img.load()
    except Exception:
        logger.exception("Thumbnail creation failed")

        return None
    img.thumbnail(THUMBNAIL_SIZES[size], resample=Resampling.LANCZOS)
    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    thumbnail_name = Path(image.name).stem + f'_thumbnail_{size}' + Path(image.name).suffix
    # Write the image to a BytesIO object
    img_byte_array = BytesIO()
    img.save(img_byte_array, format=img.format)
    thumbnail_field.save(
        thumbnail_name,
        ContentFile(img_byte_array.getvalue()),
    )
    return thumbnail_field


def get_thumbnail(image, size):
    thumbnail_field_name = get_thumbnail_field_name(image, size)
    if not (image.instance._meta.get_field(thumbnail_field_name)):
        return image

    if is_svg_filename(image.name):
        return image

    thumbnail_field = getattr(image.instance, thumbnail_field_name)
    if thumbnail_field and thumbnail_field.name:
        if not thumbnail_matches_avatar(image.name, thumbnail_field.name, size):
            thumbnail_field.delete(save=False)
            setattr(image.instance, thumbnail_field_name, None)
            thumbnail_field = None
        elif not thumbnail_field.storage.exists(thumbnail_field.name):
            thumbnail_field = None
    if not thumbnail_field:
        return create_thumbnail(image, size)
    return thumbnail_field
