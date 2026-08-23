import pytest
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from eventyay.common.image import (
    ALLOWED_IMAGE_EXTENSIONS,
    clear_avatar_thumbnails,
    create_thumbnail,
    get_thumbnail,
    process_image,
    thumbnail_matches_avatar,
    validate_image,
)


def test_allowed_image_extensions_include_webp():
    assert '.webp' in ALLOWED_IMAGE_EXTENSIONS


def test_validate_image_svg():
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    upload = SimpleUploadedFile(
        name='test.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    validate_image(upload)


def test_validate_image_svg_rejects_oversized():
    svg_content = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
        + b' ' * (2 * 1024 * 1024)
    )
    upload = SimpleUploadedFile(
        name='large.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    with pytest.raises(ValidationError, match='SVG files must be smaller'):
        validate_image(upload)


def test_validate_image_svg_rejects_script():
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    upload = SimpleUploadedFile(
        name='evil.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    with pytest.raises(ValidationError, match='disallowed content'):
        validate_image(upload)


def test_validate_image_webp():
    try:
        from PIL import Image
    except ImportError:
        pytest.skip('Pillow not available')

    image = Image.new('RGB', (8, 8), color='red')
    buffer = BytesIO()
    image.save(buffer, format='WEBP')
    upload = SimpleUploadedFile(
        name='avatar.webp',
        content=buffer.getvalue(),
        content_type='image/webp',
    )
    validate_image(upload)

class DummyField:
    def __init__(self, name):
        self.name = name

class DummyMeta:
    def get_field(self, name):
        return True

class DummyInstance:
    _meta = DummyMeta()
    def save(self, *args, **kwargs):
        pass

class DummyImage:
    def __init__(self, name):
        self.name = name
        self.instance = DummyInstance()
        self.field = DummyField('avatar')

def test_process_image_svg():
    image = DummyImage('avatar.svg')
    # Should return early without exceptions
    process_image(image=image, generate_thumbnail=True)

def test_create_thumbnail_svg():
    image = DummyImage('avatar.svg')
    thumb = create_thumbnail(image, 'tiny')
    assert thumb is None

def test_get_thumbnail_svg():
    image = DummyImage('avatar.svg')
    thumb = get_thumbnail(image, 'tiny')
    assert thumb == image


def test_thumbnail_matches_avatar():
    assert thumbnail_matches_avatar('avatars/ab/CODE.png', 'avatars/cd/CODE_thumbnail_tiny.png', 'tiny')
    assert not thumbnail_matches_avatar('avatars/ab/CODE.svg', 'avatars/cd/CODE_thumbnail_tiny.png', 'tiny')
    assert not thumbnail_matches_avatar('avatars/ab/CODE.png', 'avatars/cd/OLD_thumbnail_tiny.png', 'tiny')


class DummyThumbnailField:
    def __init__(self, name=''):
        self.name = name
        self.deleted = False

    def delete(self, save=False):
        self.deleted = True
        self.name = ''


def test_clear_avatar_thumbnails():
    user = DummyInstance()
    default_thumb = DummyThumbnailField('avatars/ab/CODE_thumbnail_default.png')
    tiny_thumb = DummyThumbnailField('avatars/ab/CODE_thumbnail_tiny.png')
    user.avatar_thumbnail = default_thumb
    user.avatar_thumbnail_tiny = tiny_thumb
    clear_avatar_thumbnails(user)
    assert default_thumb.deleted
    assert tiny_thumb.deleted
    assert user.avatar_thumbnail is None
    assert user.avatar_thumbnail_tiny is None
