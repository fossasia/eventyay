import hashlib
import json
import logging
import os
import subprocess
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from django import forms
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.validators import RegexValidator
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.functional import cached_property
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps

from eventyay.base.forms import SECRET_REDACTED, SecretKeySettingsField
from eventyay.base.models import OrderPosition
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.ticketoutput import BaseTicketOutput
from eventyay.multidomain.urlreverse import build_absolute_uri
from eventyay.plugins.passbook.forms import CertificateFileField, PNGImageField, PrivateKeyField


logger = logging.getLogger('eventyay.plugins.passbook')


@dataclass(frozen=True)
class SigningMaterial:
    """Immutable container for validated Apple Wallet cryptographic credentials."""

    certificate: x509.Certificate
    certificate_pem: bytes
    private_key: pkcs7.PKCS7PrivateKeyTypes
    private_key_pem: bytes
    private_key_password: str
    wwdr_certificate: x509.Certificate
    wwdr_certificate_pem: bytes


def read_file(value) -> bytes:
    """Read binary content from a file-like object, storage path, PEM string, or raw bytes."""
    if not value:
        return b''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if hasattr(value, 'read'):
        try:
            if hasattr(value, 'seek'):
                value.seek(0)
            content = value.read()
            if hasattr(value, 'seek'):
                value.seek(0)
            if isinstance(content, str):
                return content.encode('utf-8')
            return bytes(content)
        except (AttributeError, OSError, ValueError):
            return b''
    if isinstance(value, str):
        if '-----BEGIN' in value:
            return value.encode('utf-8')
        storage_path = value[7:] if value.startswith('file://') else value
        try:
            with default_storage.open(storage_path, 'rb') as file_object:
                return file_object.read()
        except (OSError, ValueError):
            return b''
    return b''


def load_certificate(value) -> tuple[x509.Certificate, bytes]:
    """Parse an X.509 certificate from PEM or DER content and return it with PEM bytes."""
    content = read_file(value)
    try:
        cert = x509.load_pem_x509_certificate(content)
        pem_bytes = cert.public_bytes(serialization.Encoding.PEM)
        return cert, pem_bytes
    except (ValueError, TypeError):
        cert = x509.load_der_x509_certificate(content)
        pem_bytes = cert.public_bytes(serialization.Encoding.PEM)
        return cert, pem_bytes


@lru_cache(maxsize=256)
def stored_certificate_validity(value: str) -> tuple[datetime, datetime]:
    """Return cached validity datetime range for a stored certificate path."""
    cert, __ = load_certificate(value)
    return cert.not_valid_before_utc, cert.not_valid_after_utc


def certificate_validity(value) -> tuple[datetime, datetime]:
    """Return validity range (not_valid_before_utc, not_valid_after_utc) for a certificate."""
    if isinstance(value, str):
        return stored_certificate_validity(value)
    cert, __ = load_certificate(value)
    return cert.not_valid_before_utc, cert.not_valid_after_utc


def verify_certificate_chain(signing_cert: x509.Certificate, wwdr_cert: x509.Certificate) -> None:
    """Verify that the signing certificate was issued and signed by the Apple WWDR intermediate CA."""
    if signing_cert.issuer != wwdr_cert.subject:
        raise ValidationError(_('The signing certificate was not issued by the provided Apple WWDR CA certificate.'))
    try:
        pub = wwdr_cert.public_key()
        if isinstance(pub, rsa.RSAPublicKey):
            pub.verify(
                signing_cert.signature,
                signing_cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                signing_cert.signature_hash_algorithm,
            )
        elif isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(
                signing_cert.signature,
                signing_cert.tbs_certificate_bytes,
                ec.ECDSA(signing_cert.signature_hash_algorithm),
            )
    except (InvalidSignature, TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValidationError(
            _('The signing certificate signature cannot be verified with the Apple WWDR CA certificate.')
        ) from exc


def load_signing_material(certificate, private_key_data: str, password: str, wwdr_certificate) -> SigningMaterial:
    """Load, validate, and pair signing certificate, private key, and Apple WWDR intermediate CA."""
    if not certificate or not private_key_data or not wwdr_certificate:
        raise ValidationError(_('Certificate, private key, and Apple WWDR certificate are required.'))
    try:
        signing_cert, signing_pem = load_certificate(certificate)
        wwdr_cert, wwdr_pem = load_certificate(wwdr_certificate)

        key_bytes = private_key_data.encode() if isinstance(private_key_data, str) else private_key_data
        key = serialization.load_pem_private_key(
            key_bytes,
            password=password.encode() if password else None,
        )
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValidationError(_('The Apple Wallet signing credentials could not be loaded.')) from exc

    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise ValidationError(_('The Apple Wallet private key uses an unsupported algorithm.'))

    # Verify that the private key matches the signing certificate public key
    cert_pub_bytes = signing_cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_pub_bytes = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if cert_pub_bytes != key_pub_bytes:
        raise ValidationError(_('The Apple Wallet certificate does not match the private key.'))

    now = datetime.now(UTC)
    if not (signing_cert.not_valid_before_utc <= now <= signing_cert.not_valid_after_utc):
        raise ValidationError(_('The Apple Wallet signing certificate is expired or not yet valid.'))
    if not (wwdr_cert.not_valid_before_utc <= now <= wwdr_cert.not_valid_after_utc):
        raise ValidationError(_('The Apple WWDR CA certificate is expired or not yet valid.'))

    # Verify certificate chain to WWDR intermediate CA
    verify_certificate_chain(signing_cert, wwdr_cert)

    return SigningMaterial(
        certificate=signing_cert,
        certificate_pem=signing_pem,
        private_key=key,
        private_key_pem=key_bytes,
        private_key_password=password or '',
        wwdr_certificate=wwdr_cert,
        wwdr_certificate_pem=wwdr_pem,
    )


def validate_certificate_identity(material: SigningMaterial, team_identifier: str, pass_type_identifier: str) -> None:
    """Validate that the certificate explicitly contains and matches the configured Apple Team ID and Pass Type ID."""
    ou_attrs = material.certificate.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
    if not ou_attrs:
        raise ValidationError(_('The certificate does not contain an Organizational Unit (Team ID).'))
    ou_val = ou_attrs[0].value
    if team_identifier and ou_val != team_identifier:
        raise ValidationError(
            _(
                'The certificate Organizational Unit ({cert_ou}) '
                'does not match the configured Team Identifier ({team_id}).'
            ).format(cert_ou=ou_val, team_id=team_identifier)
        )

    uid_attrs = material.certificate.subject.get_attributes_for_oid(NameOID.USER_ID)
    cn_attrs = material.certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    cert_pass_type = None
    if uid_attrs:
        cert_pass_type = uid_attrs[0].value
    elif cn_attrs:
        cn_val = cn_attrs[0].value
        if cn_val.startswith('Pass Type ID: '):
            cert_pass_type = cn_val[len('Pass Type ID: '):]

    if not cert_pass_type:
        raise ValidationError(_('The certificate does not contain a recognized Pass Type ID.'))
    if pass_type_identifier and cert_pass_type != pass_type_identifier:
        raise ValidationError(
            _(
                'The certificate Pass Type ID ({cert_pass}) '
                'does not match the configured Pass Type Identifier ({pass_id}).'
            ).format(cert_pass=cert_pass_type, pass_id=pass_type_identifier)
        )


def hex_to_rgb(hex_color: str) -> str:
    """Convert a hex color string (#RRGGBB or #RGB) to Apple Wallet 'rgb(R, G, B)' format."""
    color = hex_color.lstrip('#')
    if len(color) == 3:
        color = ''.join(c * 2 for c in color)
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return f'rgb({r}, {g}, {b})'
    except (ValueError, IndexError):
        return 'rgb(27, 77, 107)'


def create_blank_png(width: int, height: int) -> bytes:
    """Generate in-memory transparent PNG bytes of specified dimensions."""
    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    out = BytesIO()
    img.save(out, 'PNG')
    return out.getvalue()


def resized_png(content: bytes, size: tuple[int, int], crop: bool = False) -> bytes:
    """Resize image content to target dimensions with optional center crop."""
    try:
        with Image.open(BytesIO(content)) as source_img:
            img = source_img.convert('RGBA')
            if crop:
                result_img = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
            else:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                background = Image.new('RGBA', size, (255, 255, 255, 0))
                offset = ((size[0] - img.size[0]) // 2, (size[1] - img.size[1]) // 2)
                background.paste(img, offset)
                result_img = background
            output = BytesIO()
            result_img.save(output, 'PNG', optimize=True)
            return output.getvalue()
    except (OSError, ValueError):
        return create_blank_png(size[0], size[1])


def sign_manifest(manifest_bytes: bytes, material: SigningMaterial) -> bytes:
    """Generate detached PKCS#7 signature over manifest bytes with signingTime authenticated attribute."""
    # Try OpenSSL first: produces full detached PKCS#7 signature with signingTime authenticated attribute
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, 'signer.pem')
            key_path = os.path.join(tmpdir, 'key.pem')
            wwdr_path = os.path.join(tmpdir, 'wwdr.pem')
            manifest_path = os.path.join(tmpdir, 'manifest.json')
            sig_path = os.path.join(tmpdir, 'signature')

            with open(cert_path, 'wb') as f:
                f.write(material.certificate_pem)
            with open(key_path, 'wb') as f:
                f.write(material.private_key_pem)
            with open(wwdr_path, 'wb') as f:
                f.write(material.wwdr_certificate_pem)
            with open(manifest_path, 'wb') as f:
                f.write(manifest_bytes)

            cmd = [
                'openssl', 'smime', '-binary', '-sign',
                '-certfile', wwdr_path,
                '-signer', cert_path,
                '-inkey', key_path,
                '-in', manifest_path,
                '-out', sig_path,
                '-outform', 'DER',
            ]
            input_bytes = None
            if material.private_key_password:
                cmd.extend(['-passin', 'stdin'])
                input_bytes = f'{material.private_key_password}\n'.encode()

            proc = subprocess.run(
                cmd,
                input=input_bytes,
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0 and os.path.exists(sig_path):
                with open(sig_path, 'rb') as f:
                    return f.read()
            stderr_msg = proc.stderr.decode(errors='replace')
            logger.warning('OpenSSL signing returned code %s: %s', proc.returncode, stderr_msg)
    except (OSError, subprocess.SubprocessError):
        logger.warning('OpenSSL signing invocation failed, falling back to cryptography builder')

    # Fallback to cryptography PKCS7 builder if OpenSSL CLI is not available
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest_bytes)
        .add_signer(material.certificate, material.private_key, hashes.SHA256())
        .add_certificate(material.wwdr_certificate)
    )
    return builder.sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )


class PassbookTicketOutput(BaseTicketOutput):
    """Ticket output generator producing signed Apple Wallet (.pkpass) passes."""

    identifier = 'passbook'
    verbose_name = _('Apple Wallet / Passbook')
    download_button_icon = 'fa-mobile'
    download_button_text = _('Apple Wallet')
    long_download_button_text = _('Add to Apple Wallet')
    multi_download_enabled = False

    @cached_property
    def global_settings(self):
        """Return cached platform-wide global settings object."""
        return GlobalSettingsObject().settings

    @property
    def team_identifier(self) -> str:
        """Return configured Apple Developer Team ID from event or global settings."""
        return (
            self.settings.get('team_identifier')
            or self.settings.get('team_id')
            or self.global_settings.get('passbook_team_id')
            or ''
        )

    @property
    def pass_type_identifier(self) -> str:
        """Return configured Apple Pass Type ID from event or global settings."""
        return (
            self.settings.get('pass_type_identifier')
            or self.settings.get('pass_type_id')
            or self.global_settings.get('passbook_pass_type_id')
            or ''
        )

    @cached_property
    def certificate_value(self):
        """Resolve pass signing certificate from event or global configuration."""
        return (
            self.settings.get('certificate', as_type=File)
            or self.event.settings.get('ticketoutput_passbook_certificate', as_type=File)
            or self.settings.get('certificate')
            or self.event.settings.get('ticketoutput_passbook_certificate')
            or self.global_settings.get('passbook_certificate_file', as_type=File)
            or self.global_settings.get('passbook_certificate_file')
        )

    @cached_property
    def private_key_value(self):
        """Resolve pass signing private key from event or global configuration."""
        return self.settings.get('private_key') or self.global_settings.get('passbook_key') or ''

    @cached_property
    def private_key_password_value(self):
        """Resolve private key password from event or global configuration."""
        return self.settings.get('private_key_password') or self.global_settings.get('passbook_key_password') or ''

    @cached_property
    def wwdr_certificate_value(self):
        """Resolve Apple WWDR intermediate CA certificate from event or global configuration."""
        return (
            self.settings.get('wwdr_certificate', as_type=File)
            or self.event.settings.get('ticketoutput_passbook_wwdr_certificate', as_type=File)
            or self.settings.get('wwdr_certificate')
            or self.event.settings.get('ticketoutput_passbook_wwdr_certificate')
            or self.global_settings.get('passbook_wwdr_certificate_file', as_type=File)
            or self.global_settings.get('passbook_wwdr_certificate_file')
        )

    @cached_property
    def signing_material(self) -> SigningMaterial:
        """Load and validate full signing material and identity matching."""
        material = load_signing_material(
            self.certificate_value,
            self.private_key_value,
            self.private_key_password_value,
            self.wwdr_certificate_value,
        )
        validate_certificate_identity(
            material,
            self.team_identifier,
            self.pass_type_identifier,
        )
        return material

    @property
    def is_configured(self) -> bool:
        """Check if all required Apple Wallet signing parameters are configured."""
        return bool(
            self.team_identifier
            and self.pass_type_identifier
            and self.certificate_value
            and self.private_key_value
            and self.wwdr_certificate_value
        )

    @property
    def is_available(self) -> bool:
        """Check whether credentials are fully configured and valid for pass generation."""
        if not self.is_configured:
            return False
        try:
            return bool(self.signing_material)
        except (ValidationError, OSError, ValueError, UnsupportedAlgorithm):
            return False

    @property
    def is_enabled(self) -> bool:
        """Check whether pass output is enabled for attendee ticket downloads."""
        return super().is_enabled and self.is_available

    @property
    def preview_allowed(self) -> bool:
        """Return whether organizer preview generation is allowed."""
        if not self.is_available:
            return False
        try:
            return bool(self.signing_material)
        except (ValidationError, OSError):
            return False

    @property
    def settings_form_fields(self) -> dict:
        """Return form fields for configuring Apple Wallet pass colors and credentials."""
        color_validator = RegexValidator(
            regex=r'^#[0-9a-fA-F]{6}$',
            message=_('Enter a color in #RRGGBB format.'),
        )
        return OrderedDict(
            list(super().settings_form_fields.items())
            + [
                (
                    'background_color',
                    forms.CharField(
                        label=_('Background color'),
                        required=False,
                        initial='#1B4D6B',
                        validators=[color_validator],
                        widget=forms.TextInput(
                            attrs={'class': 'colorpickerfield no-contrast', 'placeholder': '#1B4D6B'}
                        ),
                    ),
                ),
                (
                    'foreground_color',
                    forms.CharField(
                        label=_('Text color'),
                        required=False,
                        initial='#FFFFFF',
                        validators=[color_validator],
                        widget=forms.TextInput(
                            attrs={'class': 'colorpickerfield no-contrast', 'placeholder': '#FFFFFF'}
                        ),
                    ),
                ),
                (
                    'label_color',
                    forms.CharField(
                        label=_('Label color'),
                        required=False,
                        initial='#D9E8F0',
                        validators=[color_validator],
                        widget=forms.TextInput(
                            attrs={'class': 'colorpickerfield no-contrast', 'placeholder': '#D9E8F0'}
                        ),
                    ),
                ),
                ('icon', PNGImageField(label=_('Pass icon (PNG)'), required=False)),
                ('logo', PNGImageField(label=_('Pass logo (PNG)'), required=False)),
                (
                    'team_identifier',
                    forms.CharField(
                        label=_('Apple team identifier (optional override)'),
                        help_text=_('Leave empty to use the platform global default if configured.'),
                        required=False,
                    ),
                ),
                (
                    'pass_type_identifier',
                    forms.CharField(
                        label=_('Pass type identifier (optional override)'),
                        help_text=_('Leave empty to use the platform global default if configured.'),
                        required=False,
                    ),
                ),
                (
                    'certificate',
                    CertificateFileField(
                        label=_('Pass signing certificate (optional override)'),
                        help_text=_('Upload PEM or DER certificate.'),
                        required=False,
                    ),
                ),
                (
                    'private_key',
                    PrivateKeyField(
                        label=_('Pass signing private key (optional override)'),
                        help_text=_('PEM private key.'),
                        required=False,
                    ),
                ),
                (
                    'private_key_password',
                    SecretKeySettingsField(
                        label=_('Private key password (optional override)'),
                        required=False,
                    ),
                ),
                (
                    'wwdr_certificate',
                    CertificateFileField(
                        label=_('Apple WWDR CA certificate (optional override)'),
                        required=False,
                    ),
                ),
            ]
        )

    def settings_form_clean(self, cleaned_data: dict) -> dict:
        """Validate Apple Wallet credentials when settings form is submitted."""
        prefix = 'ticketoutput_passbook_'
        if not cleaned_data.get(f'{prefix}_enabled'):
            return cleaned_data

        priv_key = cleaned_data.get(f'{prefix}private_key')
        if priv_key == SECRET_REDACTED:
            priv_key = self.settings.get('private_key')
        pw = cleaned_data.get(f'{prefix}private_key_password')
        if pw == SECRET_REDACTED:
            pw = self.settings.get('private_key_password')

        cert = cleaned_data.get(f'{prefix}certificate') or self.certificate_value
        key_val = priv_key or self.private_key_value
        pw_val = pw or self.private_key_password_value
        wwdr = cleaned_data.get(f'{prefix}wwdr_certificate') or self.wwdr_certificate_value

        # Only validate if any credential is supplied
        if cert or key_val or wwdr:
            material = load_signing_material(cert, key_val, pw_val, wwdr)
            team_id = cleaned_data.get(f'{prefix}team_identifier') or self.team_identifier
            pass_type = cleaned_data.get(f'{prefix}pass_type_identifier') or self.pass_type_identifier
            validate_certificate_identity(material, team_id, pass_type)
        return cleaned_data

    def settings_content_render(self, request: HttpRequest) -> str:
        """Render introductory and configuration guidance template in tickets settings."""
        template = get_template('pretixplugins/passbook/form.html')
        return template.render({'request': request, 'provider_configured': self.is_configured})

    def pass_data(self, position: OrderPosition) -> dict:
        """Build dictionary representing the complete pass.json structure for an order position."""
        order = position.order
        event = position.subevent or order.event
        product_name = str(position.product.name)
        if position.variation:
            product_name = f'{product_name} – {position.variation.value}'

        utc_starts = event.date_from.astimezone(UTC)
        starts_str = f'{utc_starts:%Y-%m-%dT%H:%M:%SZ}'
        event_ticket = {
            'primaryFields': [{'key': 'event', 'label': gettext('Event'), 'value': str(event.name)}],
            'secondaryFields': [
                {'key': 'ticket', 'label': gettext('Ticket'), 'value': product_name},
                {
                    'key': 'starts',
                    'label': gettext('Starts'),
                    'value': starts_str,
                    'dateStyle': 'PKDateStyleMedium',
                    'timeStyle': 'PKDateStyleShort',
                },
            ],
            'auxiliaryFields': [],
            'backFields': [
                {'key': 'order', 'label': gettext('Order'), 'value': order.code},
                {'key': 'organizer', 'label': gettext('Organizer'), 'value': str(order.event.organizer.name)},
                {
                    'key': 'website',
                    'label': gettext('Website'),
                    'value': build_absolute_uri(order.event, 'presale:event.index'),
                },
            ],
        }
        if event.location:
            event_ticket['auxiliaryFields'].append(
                {'key': 'location', 'label': gettext('Location'), 'value': str(event.location)}
            )
        if position.seat:
            event_ticket['auxiliaryFields'].append(
                {'key': 'seat', 'label': gettext('Seat'), 'value': str(position.seat)}
            )
        if position.attendee_name:
            event_ticket['auxiliaryFields'].append(
                {'key': 'attendee', 'label': gettext('Attendee'), 'value': position.attendee_name}
            )

        barcode_dict = {
            'format': 'PKBarcodeFormatQR',
            'message': position.secret,
            'messageEncoding': 'iso-8859-1',
            'altText': position.secret,
        }

        payload = {
            'formatVersion': 1,
            'passTypeIdentifier': self.pass_type_identifier,
            'serialNumber': f'{order.event.organizer.slug}-{order.event.slug}-{order.code}-{position.positionid}',
            'teamIdentifier': self.team_identifier,
            'organizationName': str(order.event.organizer.name),
            'description': gettext('Ticket for {event}').format(event=event.name),
            'logoText': str(event.name),
            'eventTicket': event_ticket,
            'barcode': barcode_dict,
            'barcodes': [barcode_dict],
            'relevantDate': starts_str,
        }

        for key, setting, fallback in (
            ('backgroundColor', 'background_color', '#1B4D6B'),
            ('foregroundColor', 'foreground_color', '#FFFFFF'),
            ('labelColor', 'label_color', '#D9E8F0'),
        ):
            payload[key] = hex_to_rgb(self.settings.get(setting) or fallback)

        lat = event.geo_lat if event.geo_lat is not None else order.event.geo_lat
        lon = event.geo_lon if event.geo_lon is not None else order.event.geo_lon
        if lat is not None and lon is not None:
            try:
                payload['locations'] = [{'latitude': float(lat), 'longitude': float(lon)}]
            except (ValueError, TypeError):
                pass

        if event.date_to:
            utc_to = event.date_to.astimezone(UTC)
            payload['expirationDate'] = f'{utc_to:%Y-%m-%dT%H:%M:%SZ}'

        return payload

    def pass_files(self, position: OrderPosition) -> dict[str, bytes]:
        """Construct dictionary of archive files (pass.json, icons, logos) for an order position."""
        payload = json.dumps(self.pass_data(position), ensure_ascii=False, separators=(',', ':')).encode()
        files = {'pass.json': payload}

        icon_file = self.event.settings.get('ticketoutput_passbook_icon', as_type=File, binary_file=True)
        if icon_file:
            icon_content = read_file(icon_file)
        else:
            default_icon = finders.find('pretixbase/img/icons/apple-touch-icon.png')
            if default_icon and os.path.exists(default_icon):
                with open(default_icon, 'rb') as f:
                    icon_content = f.read()
            else:
                icon_content = create_blank_png(87, 87)

        for scale in (1, 2, 3):
            suffix = '' if scale == 1 else f'@{scale}x'
            files[f'icon{suffix}.png'] = resized_png(icon_content, (29 * scale, 29 * scale), crop=True)

        logo_file = self.event.settings.get('ticketoutput_passbook_logo', as_type=File, binary_file=True)
        if logo_file:
            logo_content = read_file(logo_file)
        else:
            default_logo = finders.find('common/img/logo.png')
            if default_logo and os.path.exists(default_logo):
                with open(default_logo, 'rb') as f:
                    logo_content = f.read()
            else:
                logo_content = create_blank_png(480, 150)

        for scale in (1, 2, 3):
            suffix = '' if scale == 1 else f'@{scale}x'
            files[f'logo{suffix}.png'] = resized_png(logo_content, (160 * scale, 50 * scale), crop=False)

        return files

    def generate(self, position: OrderPosition) -> tuple[str, str, bytes]:
        """Generate complete, signed .pkpass ZIP archive for an individual order position."""
        files = self.pass_files(position)
        manifest_data = {name: hashlib.sha1(content).hexdigest() for name, content in files.items()}
        manifest = json.dumps(
            manifest_data,
            separators=(',', ':'),
            sort_keys=True,
        ).encode()

        signature = sign_manifest(manifest, self.signing_material)

        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
            archive.writestr('manifest.json', manifest)
            archive.writestr('signature', signature)

        filename = f'{self.event.slug}-{position.order.code}-{position.positionid}.pkpass'
        return filename, 'application/vnd.apple.pkpass', output.getvalue()
