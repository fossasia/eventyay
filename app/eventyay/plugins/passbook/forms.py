from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SECRET_REDACTED, SecretKeySettingsField
from eventyay.common.forms.fields import ImageField
from eventyay.consts import SizeKey
from eventyay.control.forms import ClearableBasenameFileInput


class CertificateFileField(forms.FileField):
    """File upload field validating X.509 certificate in PEM or DER format."""

    widget = ClearableBasenameFileInput
    _as_type = File

    def clean(self, value, *args, **kwargs):
        """Validate uploaded file as an X.509 certificate and normalize to PEM format."""
        value = super().clean(value, *args, **kwargs)
        if not isinstance(value, UploadedFile):
            return value

        value.seek(0)
        content = value.read()
        value.seek(0)
        try:
            try:
                certificate = x509.load_pem_x509_certificate(content)
            except ValueError:
                certificate = x509.load_der_x509_certificate(content)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_('Upload a valid X.509 certificate in PEM or DER format.')) from exc

        return SimpleUploadedFile(
            'certificate.pem',
            certificate.public_bytes(serialization.Encoding.PEM),
            'application/x-pem-file',
        )


class PNGImageField(ImageField):
    """Image field restricted to PNG format for Apple Wallet passes."""

    widget = ClearableBasenameFileInput
    extensions = {'.png': ['image/png', '.png']}
    _as_type = File

    def __init__(self, *args, **kwargs):
        """Initialize PNG image field with default max upload size."""
        kwargs.setdefault('max_size', settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_IMAGE])
        super().__init__(*args, **kwargs)


class PrivateKeyWidget(forms.Textarea):
    """Textarea widget that redacts stored private key content."""

    def __init__(self, attrs=None):
        """Initialize widget with password autocomplete and 5-row height."""
        attrs = attrs or {}
        attrs.setdefault('autocomplete', 'new-password')
        attrs.setdefault('rows', 5)
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        """Redact existing private key value in widget rendering context."""
        if value:
            value = SECRET_REDACTED
        return super().get_context(name, value, attrs)


class PrivateKeyField(SecretKeySettingsField):
    """Settings form field for securely storing PEM-encoded private keys."""

    widget = PrivateKeyWidget
