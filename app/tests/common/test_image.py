import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from eventyay.common.image import validate_image, process_image, create_thumbnail, get_thumbnail

def test_validate_image_svg():
    svg_content = b'<svg width="10" height="10"></svg>'
    upload = SimpleUploadedFile(
        name='test.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    # Should not raise exception
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

