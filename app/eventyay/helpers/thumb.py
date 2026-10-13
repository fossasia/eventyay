import hashlib
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from PIL import Image, ImageOps
from PIL.Image import Resampling

from eventyay.helpers.models import Thumbnail


class ThumbnailError(Exception):
    pass


def get_sizes(size, imgsize):
    crop = False
    if size.endswith('^'):
        crop = True
        size = size[:-1]

    if 'x' in size:
        size = [int(p) for p in size.split('x')]
    else:
        size = [int(size), int(size)]

    if crop:
        wfactor = min(1, size[0] / imgsize[0])
        hfactor = min(1, size[1] / imgsize[1])
        if wfactor == hfactor:
            return (int(imgsize[0] * wfactor), int(imgsize[1] * hfactor)), (
                0,
                int((imgsize[1] * wfactor - imgsize[1] * hfactor) / 2),
                imgsize[0] * hfactor,
                int((imgsize[1] * wfactor + imgsize[1] * wfactor) / 2),
            )
        elif wfactor > hfactor:
            return (int(size[0]), int(imgsize[1] * wfactor)), (
                0,
                int((imgsize[1] * wfactor - size[1]) / 2),
                size[0],
                int((imgsize[1] * wfactor + size[1]) / 2),
            )
        else:
            return (int(imgsize[0] * hfactor), int(size[1])), (
                int((imgsize[0] * hfactor - size[0]) / 2),
                0,
                int((imgsize[0] * hfactor + size[0]) / 2),
                size[1],
            )
    else:
        wfactor = min(1, size[0] / imgsize[0])
        hfactor = min(1, size[1] / imgsize[1])
        if wfactor == hfactor:
            return (int(imgsize[0] * hfactor), int(imgsize[1] * wfactor)), None
        elif wfactor < hfactor:
            return (size[0], int(imgsize[1] * wfactor)), None
        else:
            return (int(imgsize[0] * hfactor), size[1]), None


def create_thumbnail_file(sourcename, size):
    if str(sourcename).lower().endswith('.svg'):
        source = default_storage.open(sourcename)
        content = source.read()
        
        checksum = hashlib.md5(content).hexdigest()
        name = checksum + '.' + size.replace('^', 'c') + '.svg'
        
        return name, ContentFile(content)

    source = default_storage.open(sourcename)
    image = Image.open(BytesIO(source.read()))
    try:
        image.load()
    except OSError as e:
        msg = f'Could not load image: {e}'
        raise ThumbnailError(msg) from e

    # before we calc thumbnail, we need to check and apply EXIF-orientation
    image = ImageOps.exif_transpose(image)

    scale, crop = get_sizes(size, image.size)
    image = image.resize(scale, resample=Resampling.LANCZOS)
    if crop:
        image = image.crop(crop)

    checksum = hashlib.md5(image.tobytes()).hexdigest()
    name = checksum + '.' + size.replace('^', 'c') + '.webp'
    buffer = BytesIO()
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGB')
    image.save(fp=buffer, format='WEBP', quality=80)
    return name, ContentFile(buffer.getvalue())


def create_thumbnail(sourcename, size):
    name, content = create_thumbnail_file(sourcename, size)
    try:
        with transaction.atomic():
            thumbnail = Thumbnail.objects.create(source=sourcename, size=size)
            thumbnail.thumb.save(name, content, save=False)
            thumbnail.save(update_fields=['thumb'])
    except IntegrityError:
        return Thumbnail.objects.get(source=sourcename, size=size)
    return thumbnail


def refresh_legacy_thumbnail(source, size):
    with transaction.atomic():
        thumbnail = Thumbnail.objects.select_for_update().get(source=source, size=size)
        if thumbnail.thumb.name.lower().endswith('.webp'):
            return thumbnail

        name, content = create_thumbnail_file(source, size)
        old_name = thumbnail.thumb.name
        storage = thumbnail.thumb.storage
        thumbnail.thumb.save(name, content, save=False)
        thumbnail.save(update_fields=['thumb'])
        transaction.on_commit(lambda: storage.delete(old_name))
        return thumbnail


def get_thumbnail(source, size):
    # Assumes files are immutable
    try:
        thumbnail = Thumbnail.objects.get(source=source, size=size)
    except Thumbnail.DoesNotExist:
        return create_thumbnail(source, size)

    if not str(source).lower().endswith('.svg') and not thumbnail.thumb.name.lower().endswith('.webp'):
        return refresh_legacy_thumbnail(source, size)

    return thumbnail
