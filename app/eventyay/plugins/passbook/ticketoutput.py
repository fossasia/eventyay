import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
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
from eventyay.base.ticketoutput import BaseTicketOutput
from eventyay.multidomain.urlreverse import build_absolute_uri
from eventyay.plugins.passbook.forms import CertificateFileField, PNGImageField, PrivateKeyField


@dataclass(frozen=True)
class SigningMaterial:
    certificate: x509.Certificate
    private_key: pkcs7.PKCS7PrivateKeyTypes
    wwdr_certificate: x509.Certificate


def read_file(value) -> bytes:
    if isinstance(value, str):
        with default_storage.open(value, 'rb') as file_object:
            return file_object.read()
    if isinstance(value, File):
        value.open('rb')
    value.seek(0)
    content = value.read()
    value.seek(0)
    return content


def load_certificate(value) -> x509.Certificate:
    content = read_file(value)
    try:
        return x509.load_pem_x509_certificate(content)
    except ValueError:
        return x509.load_der_x509_certificate(content)


def load_signing_material(certificate, private_key: str, password: str, wwdr_certificate) -> SigningMaterial:
    if not certificate or not private_key or not wwdr_certificate:
        raise ValidationError(_('Certificate, private key, and WWDR certificate are required.'))
    try:
        signing_certificate = load_certificate(certificate)
        wwdr = load_certificate(wwdr_certificate)
        key = serialization.load_pem_private_key(
            private_key.encode(),
            password=password.encode() if password else None,
        )
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValidationError(_('The Apple Wallet signing credentials are invalid.')) from exc
    if not isinstance(key, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
        raise ValidationError(_('The Apple Wallet private key uses an unsupported algorithm.'))

    now = datetime.now(UTC)
    if not signing_certificate.not_valid_before_utc <= now <= signing_certificate.not_valid_after_utc:
        raise ValidationError(_('The Apple Wallet signing certificate is not currently valid.'))
    if not wwdr.not_valid_before_utc <= now <= wwdr.not_valid_after_utc:
        raise ValidationError(_('The WWDR certificate is not currently valid.'))

    certificate_public_key = signing_certificate.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_public_key = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if certificate_public_key != private_public_key:
        raise ValidationError(_('The private key does not match the signing certificate.'))
    return SigningMaterial(signing_certificate, key, wwdr)


def validate_certificate_identity(material: SigningMaterial, team_identifier: str, pass_type_identifier: str) -> None:
    try:
        certificate_team = material.certificate.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)[
            0
        ].value
        certificate_pass_type = material.certificate.subject.get_attributes_for_oid(NameOID.USER_ID)[0].value
    except IndexError as exc:
        raise ValidationError(_('The signing certificate does not contain Apple Wallet identifiers.')) from exc
    if certificate_team != team_identifier:
        raise ValidationError(_('The team identifier does not match the signing certificate.'))
    if certificate_pass_type != pass_type_identifier:
        raise ValidationError(_('The pass type identifier does not match the signing certificate.'))
    try:
        constraints = material.wwdr_certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
        if not constraints.ca:
            raise ValidationError(_('The WWDR certificate is not a certificate authority.'))
        material.certificate.verify_directly_issued_by(material.wwdr_certificate)
    except x509.ExtensionNotFound as exc:
        raise ValidationError(_('The WWDR certificate is missing certificate authority data.')) from exc
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise ValidationError(_('The signing certificate was not issued by the WWDR certificate.')) from exc


def rgb_color(value: str) -> str:
    value = value.lstrip('#')
    return f'rgb({int(value[0:2], 16)}, {int(value[2:4], 16)}, {int(value[4:6], 16)})'


def resized_png(content: bytes, size: tuple[int, int], crop: bool = False) -> bytes:
    with Image.open(BytesIO(content)) as source:
        image = source.convert('RGBA')
        if crop:
            image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        else:
            image.thumbnail(size, Image.Resampling.LANCZOS)
            canvas = Image.new('RGBA', size)
            canvas.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
            image = canvas
        output = BytesIO()
        image.save(output, 'PNG', optimize=True)
        return output.getvalue()


class PassbookTicketOutput(BaseTicketOutput):
    identifier = 'passbook'
    verbose_name = _('Apple Wallet')
    download_button_icon = 'fa-mobile'
    download_button_text = _('Apple Wallet')
    long_download_button_text = _('Add to Apple Wallet')
    multi_download_enabled = False

    @cached_property
    def signing_material(self) -> SigningMaterial:
        material = load_signing_material(
            self.event.settings.get('ticketoutput_passbook_certificate', as_type=File),
            self.settings.get('private_key'),
            self.settings.get('private_key_password'),
            self.event.settings.get('ticketoutput_passbook_wwdr_certificate', as_type=File),
        )
        validate_certificate_identity(
            material,
            self.settings.get('team_identifier'),
            self.settings.get('pass_type_identifier'),
        )
        return material

    @property
    def is_configured(self) -> bool:
        if not self.settings.get('team_identifier') or not self.settings.get('pass_type_identifier'):
            return False
        try:
            self.signing_material
        except (ValidationError, OSError):
            return False
        return True

    @property
    def is_enabled(self) -> bool:
        return super().is_enabled and self.is_configured

    @property
    def preview_allowed(self) -> bool:
        return self.is_configured

    @property
    def settings_form_fields(self) -> dict:
        color_validator = RegexValidator(
            regex=r'^#[0-9a-fA-F]{6}$',
            message=_('Enter a color in #RRGGBB format.'),
        )
        return OrderedDict(
            list(super().settings_form_fields.items())
            + [
                ('team_identifier', forms.CharField(label=_('Apple team identifier'), required=True)),
                ('pass_type_identifier', forms.CharField(label=_('Pass type identifier'), required=True)),
                (
                    'certificate',
                    CertificateFileField(label=_('Pass signing certificate'), required=True),
                ),
                (
                    'private_key',
                    PrivateKeyField(label=_('Pass signing private key'), required=True),
                ),
                (
                    'private_key_password',
                    SecretKeySettingsField(label=_('Private key password'), required=False),
                ),
                (
                    'wwdr_certificate',
                    CertificateFileField(label=_('Apple WWDR certificate'), required=True),
                ),
                ('icon', PNGImageField(label=_('Pass icon'), required=False)),
                ('logo', PNGImageField(label=_('Pass logo'), required=False)),
                (
                    'background_color',
                    forms.CharField(
                        label=_('Background color'),
                        required=False,
                        initial='#1B4D6B',
                        validators=[color_validator],
                    ),
                ),
                (
                    'foreground_color',
                    forms.CharField(
                        label=_('Text color'),
                        required=False,
                        initial='#FFFFFF',
                        validators=[color_validator],
                    ),
                ),
                (
                    'label_color',
                    forms.CharField(
                        label=_('Label color'),
                        required=False,
                        initial='#D9E8F0',
                        validators=[color_validator],
                    ),
                ),
            ]
        )

    def settings_form_clean(self, cleaned_data: dict) -> dict:
        prefix = 'ticketoutput_passbook_'
        if not cleaned_data.get(f'{prefix}_enabled'):
            return cleaned_data

        private_key = cleaned_data.get(f'{prefix}private_key')
        if private_key == SECRET_REDACTED:
            private_key = self.settings.get('private_key')
        password = cleaned_data.get(f'{prefix}private_key_password')
        if password == SECRET_REDACTED:
            password = self.settings.get('private_key_password')

        material = load_signing_material(
            cleaned_data.get(f'{prefix}certificate'),
            private_key,
            password,
            cleaned_data.get(f'{prefix}wwdr_certificate'),
        )
        validate_certificate_identity(
            material,
            cleaned_data.get(f'{prefix}team_identifier'),
            cleaned_data.get(f'{prefix}pass_type_identifier'),
        )
        return cleaned_data

    def settings_content_render(self, request: HttpRequest) -> str:
        template = get_template('pretixplugins/passbook/form.html')
        return template.render({'request': request, 'provider_configured': self.is_configured})

    def pass_data(self, position: OrderPosition) -> dict:
        order = position.order
        event = position.subevent or order.event
        product_name = f'{position.product.name}'
        if position.variation:
            product_name = f'{product_name} – {position.variation.value}'

        event_ticket = {
            'primaryFields': [{'key': 'event', 'label': gettext('Event'), 'value': f'{event.name}'}],
            'secondaryFields': [{'key': 'ticket', 'label': gettext('Ticket'), 'value': product_name}],
            'auxiliaryFields': [],
            'backFields': [
                {'key': 'order', 'label': gettext('Order'), 'value': order.code},
                {'key': 'organizer', 'label': gettext('Organizer'), 'value': f'{order.event.organizer.name}'},
                {
                    'key': 'website',
                    'label': gettext('Website'),
                    'value': build_absolute_uri(order.event, 'presale:event.index'),
                },
            ],
        }
        if position.seat:
            event_ticket['auxiliaryFields'].append(
                {'key': 'seat', 'label': gettext('Seat'), 'value': f'{position.seat}'}
            )
        elif position.attendee_name:
            event_ticket['auxiliaryFields'].append(
                {'key': 'attendee', 'label': gettext('Attendee'), 'value': position.attendee_name}
            )

        payload = {
            'formatVersion': 1,
            'passTypeIdentifier': self.settings.get('pass_type_identifier'),
            'serialNumber': f'{order.event.organizer.slug}-{order.event.slug}-{order.code}-{position.positionid}',
            'teamIdentifier': self.settings.get('team_identifier'),
            'organizationName': f'{order.event.organizer.name}',
            'description': gettext('Ticket for {event}').format(event=event.name),
            'logoText': f'{event.name}',
            'eventTicket': event_ticket,
            'barcodes': [
                {
                    'format': 'PKBarcodeFormatQR',
                    'message': position.secret,
                    'messageEncoding': 'iso-8859-1',
                    'altText': position.secret,
                }
            ],
            'relevantDate': event.date_from.isoformat(),
        }
        for key, setting, fallback in (
            ('backgroundColor', 'background_color', '#1B4D6B'),
            ('foregroundColor', 'foreground_color', '#FFFFFF'),
            ('labelColor', 'label_color', '#D9E8F0'),
        ):
            payload[key] = rgb_color(self.settings.get(setting) or fallback)

        latitude = event.geo_lat if event.geo_lat is not None else order.event.geo_lat
        longitude = event.geo_lon if event.geo_lon is not None else order.event.geo_lon
        if latitude is not None and longitude is not None:
            payload['locations'] = [{'latitude': float(latitude), 'longitude': float(longitude)}]
        if event.date_to:
            payload['expirationDate'] = event.date_to.isoformat()
        return payload

    def pass_files(self, position: OrderPosition) -> dict[str, bytes]:
        payload = json.dumps(self.pass_data(position), ensure_ascii=False, separators=(',', ':')).encode()
        files = {'pass.json': payload}
        icon = self.event.settings.get('ticketoutput_passbook_icon', as_type=File)
        logo = self.event.settings.get('ticketoutput_passbook_logo', as_type=File)
        if icon:
            icon_content = read_file(icon)
        else:
            with open(finders.find('pretixbase/img/icons/apple-touch-icon.png'), 'rb') as icon_file:
                icon_content = icon_file.read()
        for scale in (1, 2, 3):
            suffix = '' if scale == 1 else f'@{scale}x'
            files[f'icon{suffix}.png'] = resized_png(icon_content, (29 * scale, 29 * scale), crop=True)
        if logo:
            logo_content = read_file(logo)
            for scale in (1, 2, 3):
                suffix = '' if scale == 1 else f'@{scale}x'
                files[f'logo{suffix}.png'] = resized_png(logo_content, (160 * scale, 50 * scale))
        return files

    def generate(self, position: OrderPosition) -> tuple[str, str, bytes]:
        files = self.pass_files(position)
        manifest = json.dumps(
            {name: hashlib.sha1(content).hexdigest() for name, content in files.items()},
            separators=(',', ':'),
            sort_keys=True,
        ).encode()
        material = self.signing_material
        signature = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(manifest)
            .add_signer(material.certificate, material.private_key, hashes.SHA256())
            .add_certificate(material.wwdr_certificate)
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
            )
        )

        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
            archive.writestr('manifest.json', manifest)
            archive.writestr('signature', signature)
        return (
            f'{self.event.slug}-{position.order.code}-{position.positionid}.pkpass',
            'application/vnd.apple.pkpass',
            output.getvalue(),
        )
