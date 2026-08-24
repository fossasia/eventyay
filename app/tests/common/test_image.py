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
    recompress_image_field,
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

def test_validate_image_svg_rejects_data_uri():
    svg_content = b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><a xlink:href="data:text/html,test">test</a></svg>'
    upload = SimpleUploadedFile(
        name='data.svg',
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
    assert process_image(image=image, generate_thumbnail=True) is True


def test_process_image_gif_skips_original_rewrite(tmp_path):
    from PIL import Image

    image_path = tmp_path / 'avatar.gif'
    img = Image.new('RGB', (400, 400), color='green')
    img.save(image_path, format='GIF')

    class DummyImageFile:
        def __init__(self, path):
            self.path = str(path)
            self.name = 'avatar.gif'

    assert process_image(image=DummyImageFile(image_path), generate_thumbnail=False) is True
    assert Image.open(image_path).format == 'GIF'


def test_recompress_image_field_returns_false_when_processing_fails():
    class BrokenImage:
        name = 'avatar.jpg'
        path = '/does/not/exist/avatar.jpg'

        @property
        def size(self):
            return 1024 * 1024

    assert recompress_image_field(BrokenImage()) is False

def test_process_image_webp(tmp_path):
    from PIL import Image
    image_path = tmp_path / 'avatar.webp'
    img = Image.new('RGB', (800, 800), color='red')
    img.save(image_path, format='WEBP')

    class DummyImageFile:
        def __init__(self, path):
            self.path = str(path)
            self.name = 'avatar.webp'

    process_image(image=DummyImageFile(image_path), generate_thumbnail=False)
    
    processed = Image.open(image_path)
    assert processed.format == 'WEBP'

def test_noisy_jpeg_compression_and_thumbs(tmp_path):
    from PIL import Image
    import os
    import random
    
    image_path = tmp_path / 'avatar.jpg'
    img = Image.new('RGB', (2000, 2000))
    # generate a somewhat noisy image to prevent over-compression by solid colors
    # we don't need a full loop, just random blocks is enough to simulate detail
    import PIL.ImageDraw as ImageDraw
    draw = ImageDraw.Draw(img)
    for i in range(100):
        x0 = random.randint(0, 1900)
        y0 = random.randint(0, 1900)
        draw.rectangle([x0, y0, x0+100, y0+100], fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        
    img.save(image_path, format='JPEG', quality=100)
    
    original_size = os.path.getsize(image_path)
    
    class DummyFieldSave:
        def __init__(self, name):
            self.name = name
            
        def save(self, name, content):
            with open(tmp_path / name, 'wb') as f:
                f.write(content.read())

    class DummyInstanceSave:
        _meta = DummyMeta()
        def __init__(self):
            self.avatar_thumbnail_tiny = DummyFieldSave('avatar_thumbnail_tiny')
            self.avatar_thumbnail = DummyFieldSave('avatar_thumbnail')
            self.avatar_thumbnail_tiny_thumbnail_tiny = DummyFieldSave('dummy') # satisfy hasattr check

    class DummyImageFileSave:
        def __init__(self, path):
            self.path = str(path)
            self.name = 'avatar.jpg'
            self.instance = DummyInstanceSave()
            self.field = DummyField('avatar')

    dummy_image = DummyImageFileSave(image_path)
    process_image(image=dummy_image, generate_thumbnail=True)
    
    processed_size = os.path.getsize(image_path)
    assert processed_size < original_size
    
    tiny_size = os.path.getsize(tmp_path / 'avatar_thumbnail_tiny.jpg')
    default_size = os.path.getsize(tmp_path / 'avatar_thumbnail_default.jpg')
    
    assert tiny_size < 20000, f"Tiny thumb is {tiny_size} bytes, expected < 20000"
    assert default_size < 80000, f"Default thumb is {default_size} bytes, expected < 80000"


def test_recompress_image_field_skips_svg():
    image = DummyImage('avatar.svg')
    assert recompress_image_field(image) is False


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
    assert thumbnail_matches_avatar('avatars/ab/CODE.png', 'avatars/cd/CODE_thumbnail_tiny.jpg', 'tiny')


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
