from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from eventyay.helpers.image_optimize import (
    MAX_WIDTH,
    OptimizedImages,
    optimize_uploaded_image,
)


def _create_test_image(width: int, height: int, mode: str = 'RGB', format: str = 'JPEG', color='red') -> SimpleUploadedFile:
    img = Image.new(mode, (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(
        name=f'test.{format.lower()}',
        content=buf.read(),
        content_type=f'image/{format.lower()}',
    )


@pytest.mark.parametrize('setting_key', ['logo_image', 'event_logo_image', 'event_preview_image', 'organizer_logo_image', 'organizer_header_image', 'og_image', 'picture'])
def test_optimize_uploaded_image_resizes(setting_key):
    max_w = MAX_WIDTH[setting_key]
    orig_w = max_w + 500
    orig_h = max_w

    upload = _create_test_image(orig_w, orig_h)
    result = optimize_uploaded_image(upload, setting_key)

    assert isinstance(result, OptimizedImages)

    # Check optimized file
    opt_img = Image.open(result.optimized)
    assert opt_img.size[0] == max_w
    # height should scale proportionally, allow 1px rounding diff
    expected_h = int(orig_h * (max_w / orig_w))
    assert abs(opt_img.size[1] - expected_h) <= 1

    # Check original file
    orig_img = Image.open(result.original)
    assert orig_img.size == (orig_w, orig_h)

    # Extensions
    assert result.optimized_ext == 'webp'
    assert result.original_ext == 'jpeg'


def test_optimize_uploaded_image_preserves_alpha_in_webp():
    img = Image.new('RGBA', (800, 600), color=(255, 0, 0, 255))
    # Make top left corner partially transparent and next pixel fully transparent
    img.putpixel((0, 0), (0, 255, 0, 128))
    img.putpixel((1, 1), (0, 0, 255, 0))
    
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    upload = SimpleUploadedFile(
        name='test.png',
        content=buf.read(),
        content_type='image/png',
    )
    
    result = optimize_uploaded_image(upload, 'event_logo_image')

    opt_img = Image.open(result.optimized)
    assert opt_img.format == 'WEBP'
    assert result.optimized_ext == 'webp'
    
    opt_img_rgba = opt_img.convert('RGBA')
    pixel_partial = opt_img_rgba.getpixel((0, 0))
    pixel_full = opt_img_rgba.getpixel((1, 1))
    
    # WebP lossy encoding might slightly shift alpha values, but they should be close
    assert 100 < pixel_partial[3] < 150
    assert 0 <= pixel_full[3] < 10


@pytest.mark.parametrize("mode,color_bg,color_fg,transparency_val", [
    ('P', 0, 1, 0),
    ('L', 0, 255, 0),
    ('RGB', (255, 0, 0), (0, 255, 0), (255, 0, 0)),
])
def test_optimize_uploaded_image_preserves_metadata_transparency(mode, color_bg, color_fg, transparency_val):
    # Create an image with metadata transparency
    img = Image.new(mode, (800, 600), color=color_bg)
    if mode == 'P':
        img.putpalette([255, 0, 0, 0, 255, 0])  # index 0 is red, index 1 is green
    img.putpixel((1, 1), color_fg)
    
    buf = BytesIO()
    # Save with transparency_val as transparent
    img.save(buf, format='PNG', transparency=transparency_val)
    buf.seek(0)
    
    upload = SimpleUploadedFile(
        name='test_palette.png',
        content=buf.read(),
        content_type='image/png',
    )
    
    result = optimize_uploaded_image(upload, 'event_logo_image')
    opt_img = Image.open(result.optimized)
    
    assert opt_img.format == 'WEBP'
    assert result.optimized_ext == 'webp'
    
    opt_img_rgba = opt_img.convert('RGBA')
    pixel_transparent = opt_img_rgba.getpixel((0, 0))
    pixel_opaque = opt_img_rgba.getpixel((1, 1))
    
    # Check that transparency survived in WebP
    assert pixel_transparent[3] == 0
    assert pixel_opaque[3] == 255


def test_optimize_uploaded_image_converts_bmp_to_jpg():
    upload = _create_test_image(800, 600, mode='RGB', format='BMP')
    upload.name = 'test.bmp'
    result = optimize_uploaded_image(upload, 'logo_image')

    opt_img = Image.open(result.optimized)
    assert opt_img.format == 'WEBP'
    assert result.optimized_ext == 'webp'
    assert result.original_ext == 'bmp'


def test_optimize_uploaded_image_invalid_key():
    upload = _create_test_image(100, 100)
    with pytest.raises(ValueError, match='Unknown image setting key'):
        optimize_uploaded_image(upload, 'invalid_key')


def test_optimize_uploaded_image_invalid_image():
    upload = SimpleUploadedFile(
        name='test.jpg',
        content=b'not an image file',
        content_type='image/jpeg',
    )
    with pytest.raises(OSError):
        optimize_uploaded_image(upload, 'logo_image')


def test_optimize_uploaded_image_preserves_animated_gif():
    # Create an animated GIF with width > MAX_WIDTH
    img1 = Image.new('RGB', (4000, 4000), 'red')
    img2 = Image.new('RGB', (4000, 4000), 'blue')
    buf = BytesIO()
    img1.save(buf, format='GIF', save_all=True, append_images=[img2], duration=100, loop=0)
    buf.seek(0)

    upload = SimpleUploadedFile(
        name='test.gif',
        content=buf.read(),
        content_type='image/gif',
    )

    result = optimize_uploaded_image(upload, 'logo_image')

    # Assert that the image was not resized, even though it's 4000x4000
    # and the max width for logo_image is 3000
    opt_img = Image.open(result.optimized)
    assert opt_img.size == (4000, 4000)
    assert getattr(opt_img, 'is_animated', False)
    assert result.optimized_ext == 'gif'

def test_optimize_uploaded_image_bypasses_svg():
    svg_content = b'<svg width="10" height="10"></svg>'
    upload = SimpleUploadedFile(
        name='test.svg',
        content=svg_content,
        content_type='image/svg+xml',
    )
    result = optimize_uploaded_image(upload, 'logo_image')
    assert result.optimized_ext == 'svg'
    assert result.original_ext == 'svg'
    assert result.optimized.read() == svg_content
    assert result.original.read() == svg_content
