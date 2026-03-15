from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import TestCase

from django.core.exceptions import ValidationError
from PIL import Image

from eventyay.base.image_safety import MAX_IMAGE_PIXELS, validate_image


class TestSafeImageReader(TestCase):

    def test_real_image_success(self):
        """
        Test using a real (in-memory) image to demonstrate realistic behavior without mocks.
        This addresses the PR feedback to ensure the logic works against real Pillow processing.
        """
        img = Image.new('RGB', (10, 10))
        file_obj = BytesIO()
        img.save(file_obj, format='JPEG')
        file_obj.seek(0)

        # No mocks here; relies on actual Pillow implementation
        validate_image(file_obj)

    def test_real_corrupted_image(self):
        """
        Test using real bad data to prove Pillow correctly raises exceptions
        that we catch and wrap in a ValidationError.
        """
        file_obj = BytesIO(b"This is not a real image, just some random bytes.")
        with self.assertRaises(ValidationError) as cm:
            validate_image(file_obj)
        self.assertIn('Invalid or corrupted image file', str(cm.exception))

    @patch('eventyay.base.image_safety.Image.open')
    def test_valid_image(self, mock_open):
        """Test that a valid small image is accepted."""
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img.format = 'JPEG'
        mock_open.return_value.__enter__.return_value = mock_img

        file_obj = BytesIO(b'fake_image_data')
        validate_image(file_obj)
        self.assertEqual(file_obj.tell(), 0)

    @patch('eventyay.base.image_safety.Image.open')
    def test_valid_image_from_filepath(self, mock_open):
        """Test that passing a string (filepath) doesn't crash on seek."""
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img.format = 'JPEG'
        mock_open.return_value.__enter__.return_value = mock_img

        validate_image('/fake/path/image.jpg')

    @patch('eventyay.base.image_safety.Image.open')
    def test_image_at_max_pixel_limit(self, mock_open):
        """Test that an image at the exact MAX_IMAGE_PIXELS boundary is accepted."""
        mock_img = MagicMock()
        mock_img.size = (MAX_IMAGE_PIXELS, 1)
        mock_img.format = 'JPEG'
        mock_open.return_value.__enter__.return_value = mock_img

        file_obj = BytesIO(b'boundary_image_data')
        validate_image(file_obj)

    @patch('eventyay.base.image_safety.Image.open')
    def test_image_too_large(self, mock_open):
        """
        Test that an image exceeding the pixel limit is rejected.
        Justification for Mock: We mock Image.open here because creating or committing
        a real >25 Megapixel image would unnecessarily consume memory and bloat the git repository.
        """
        mock_img = MagicMock()
        mock_img.size = (6000, 5000)  # 30MP > 25MP limit
        mock_img.format = 'JPEG'
        mock_open.return_value.__enter__.return_value = mock_img

        file_obj = BytesIO(b'huge_image_data')

        with self.assertRaises(ValidationError) as cm:
            validate_image(file_obj)

        self.assertIn('Image is too large', str(cm.exception))

    def test_invalid_format(self):
        """
        Test that an unsupported real image format (e.g. WEBP) is rejected.
        Because Pillow's Image.open is restricted to ALLOWED_FORMATS, it
        will fail to find a matching decoder for WEBP and raise an 
        UnidentifiedImageError (a subclass of OSError). SafeImageReader 
        catches this and wraps it in a ValidationError.
        """
        img = Image.new('RGB', (10, 10))
        file_obj = BytesIO()
        img.save(file_obj, format='WEBP')
        file_obj.seek(0)

        with self.assertRaises(ValidationError) as cm:
            validate_image(file_obj)

        self.assertIn('Invalid or corrupted image file', str(cm.exception))

    @patch('eventyay.base.image_safety.Image.open')
    def test_valid_bmp_and_tiff_formats(self, mock_open):
        """Test that BMP and TIFF formats are accepted (legacy support)."""
        mock_img = MagicMock()
        mock_img.size = (100, 100)
        mock_img.format = 'BMP'
        mock_open.return_value.__enter__.return_value = mock_img

        file_obj = BytesIO(b'bmp_data')
        validate_image(file_obj)

        mock_img.format = 'TIFF'
        file_obj = BytesIO(b'tiff_data')
        validate_image(file_obj)

    @patch('eventyay.base.image_safety.Image.open')
    def test_invalid_file_content(self, mock_open):
        """Test that a corrupted file raises ValidationError."""
        # Use SyntaxError as Pillow often raises it for corrupt files,
        # or Exception to simulate an arbitrary failure
        mock_open.side_effect = SyntaxError('Corrupt file')
        file_obj = BytesIO(b'not_an_image')

        with self.assertRaises(ValidationError):
            validate_image(file_obj)


