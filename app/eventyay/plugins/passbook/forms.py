from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from eventyay.base.forms import SECRET_REDACTED, SecretKeySettingsField
from eventyay.control.forms import ClearableBasenameFileInput


class CertificateFileField(forms.FileField):
    widget = ClearableBasenameFileInput

    def clean(self, value, *args, **kwargs):
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
        except ValueError as exc:
            raise ValidationError(_('Upload a valid X.509 certificate in PEM or DER format.')) from exc

        return SimpleUploadedFile(
            'certificate.pem',
            certificate.public_bytes(serialization.Encoding.PEM),
            'application/x-pem-file',
        )


class PNGImageField(forms.FileField):
    widget = ClearableBasenameFileInput

    def clean(self, value, *args, **kwargs):
        value = super().clean(value, *args, **kwargs)
        if not isinstance(value, UploadedFile):
            return value

        value.seek(0)
        try:
            with Image.open(value) as image:
                if image.format != 'PNG':
                    raise ValidationError(_('Upload a PNG image.'))
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValidationError(_('Upload a valid PNG image.')) from exc
        finally:
            value.seek(0)
        return value


class PrivateKeyWidget(forms.Textarea):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.setdefault('autocomplete', 'new-password')
        attrs.setdefault('rows', 5)
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        if value:
            value = SECRET_REDACTED
        return super().get_context(name, value, attrs)


class PrivateKeyField(SecretKeySettingsField):
    widget = PrivateKeyWidget
