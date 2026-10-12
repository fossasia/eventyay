import json
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from django_scopes import scope
from rest_framework.test import APIRequestFactory

from eventyay.api.serializers.order import OrderDownloadsField
from eventyay.base.email import get_combined_ticket_output_identifier
from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
)
from eventyay.base.models import (
    Product as Item,
)
from eventyay.base.plugins import get_all_plugins
from eventyay.base.signals import register_ticket_outputs
from eventyay.plugins.passbook.apps import PassbookApp
from eventyay.plugins.passbook.forms import CertificateFileField, PNGImageField, PrivateKeyWidget
from eventyay.plugins.passbook.ticketoutput import (
    PassbookTicketOutput,
    SigningMaterial,
    create_blank_png,
    hex_to_rgb,
    load_certificate,
    load_signing_material,
    read_file,
    sign_manifest,
    validate_certificate_identity,
)


@pytest.fixture
def test_certs():
    # 1. Generate CA (mimicking Apple WWDR CA)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Apple Inc.'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'Apple Worldwide Developer Relations Certification Authority'),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # 2. Generate Signer Key and Cert
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'TEAM123456'),
        x509.NameAttribute(NameOID.USER_ID, 'pass.eventyay.ticket'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'Pass Type ID: pass.eventyay.ticket'),
    ])
    signer_cert = (
        x509.CertificateBuilder()
        .subject_name(signer_name)
        .issuer_name(ca_name)
        .public_key(signer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    signer_pem = signer_cert.public_bytes(serialization.Encoding.PEM)
    signer_key_pem = signer_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    return {
        'ca_cert': ca_cert,
        'ca_pem': ca_pem,
        'signer_cert': signer_cert,
        'signer_pem': signer_pem,
        'signer_key': signer_key,
        'signer_key_pem': signer_key_pem,
    }


@pytest.fixture
def env(test_certs):
    o = Organizer.objects.create(name='Passbook Org', slug='passbook-org')
    event = Event.objects.create(
        organizer=o,
        name='Passbook Event',
        slug='passbook-event',
        date_from=now(),
        date_to=now() + timedelta(days=1),
        plugins='eventyay.plugins.passbook',
        live=True,
    )
    with scope(organizer=o, event=event):
        order = Order.objects.create(
            code='PB001',
            event=event,
            email='attendee@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('25.00'),
        )
        ticket_item = Item.objects.create(event=event, name='Conference Pass', default_price=25)
        pos = OrderPosition.objects.create(
            order=order,
            product=ticket_item,
            price=25,
            attendee_name_parts={'full_name': 'Jane Doe'},
            secret='PASSBOOK_SECRET_XYZ_123',
        )
        return o, event, order, pos


@pytest.mark.django_db
def test_plugin_metadata_and_registration(env):
    o, event, order, pos = env
    app_config = apps.get_app_config('passbook')
    assert isinstance(app_config, PassbookApp)
    assert app_config.verbose_name == 'Passbook / Apple Wallet tickets'

    all_plugins = [p.name for p in get_all_plugins()]
    assert 'Apple Wallet / Passbook' in all_plugins

    with scope(organizer=o, event=event):
        responses = register_ticket_outputs.send(event)
        output_classes = [r[1] for r in responses]
        assert PassbookTicketOutput in output_classes


@pytest.mark.django_db
def test_output_properties_and_defaults(env, test_certs):
    o, event, order, pos = env
    with scope(organizer=o, event=event):
        output = PassbookTicketOutput(event)
        assert output.identifier == 'passbook'
        assert output.multi_download_enabled is False
        assert output.download_button_icon == 'fa-mobile'
        assert str(output.verbose_name) == 'Apple Wallet / Passbook'
        assert str(output.download_button_text) == 'Apple Wallet'
        assert output.is_configured is False
        assert output.is_available is False
        assert output.is_enabled is False

        cert_path = default_storage.save('pub/test_cert_defaults.pem', ContentFile(test_certs['signer_pem']))
        wwdr_path = default_storage.save('pub/test_wwdr_defaults.pem', ContentFile(test_certs['ca_pem']))
        event.settings.set('ticketoutput_passbook_team_identifier', 'TEAM123456')
        event.settings.set('ticketoutput_passbook_pass_type_identifier', 'pass.eventyay.ticket')
        event.settings.set('ticketoutput_passbook_certificate', f'file://{cert_path}')
        event.settings.set('ticketoutput_passbook_private_key', test_certs['signer_key_pem'].decode())
        event.settings.set('ticketoutput_passbook_wwdr_certificate', f'file://{wwdr_path}')

        configured_output = PassbookTicketOutput(event)
        assert configured_output.is_configured is True
        assert configured_output.is_available is True
        assert configured_output.is_enabled is True


def test_hex_to_rgb():
    assert hex_to_rgb('#ffffff') == 'rgb(255, 255, 255)'
    assert hex_to_rgb('#000000') == 'rgb(0, 0, 0)'
    assert hex_to_rgb('#1b4d6b') == 'rgb(27, 77, 107)'
    assert hex_to_rgb('#fff') == 'rgb(255, 255, 255)'
    assert hex_to_rgb('invalid') == 'rgb(27, 77, 107)'


def test_load_certificate_and_signing_material(test_certs):
    cert, pem = load_certificate(test_certs['signer_pem'])
    assert isinstance(cert, x509.Certificate)
    assert pem.startswith(b'-----BEGIN CERTIFICATE-----')

    material = load_signing_material(
        certificate=ContentFile(test_certs['signer_pem']),
        private_key_data=test_certs['signer_key_pem'].decode(),
        password='',
        wwdr_certificate=ContentFile(test_certs['ca_pem']),
    )
    assert isinstance(material, SigningMaterial)
    assert material.certificate == cert

    validate_certificate_identity(material, team_identifier='TEAM123456', pass_type_identifier='pass.eventyay.ticket')

    with pytest.raises(ValidationError) as exc:
        validate_certificate_identity(
            material,
            team_identifier='WRONG_TEAM',
            pass_type_identifier='pass.eventyay.ticket',
        )
    assert 'does not match the configured Team Identifier' in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_certificate_identity(
            material,
            team_identifier='TEAM123456',
            pass_type_identifier='pass.wrong.id',
        )
    assert 'does not match the configured Pass Type Identifier' in str(exc.value)


def test_expired_certificate_raises_validation_error(test_certs):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Test CA')])

    expired_signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    expired_signer_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, 'TEAM123456'),
        x509.NameAttribute(NameOID.USER_ID, 'pass.eventyay.ticket'),
    ])
    expired_signer_cert = (
        x509.CertificateBuilder()
        .subject_name(expired_signer_name)
        .issuer_name(ca_name)
        .public_key(expired_signer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=100))
        .not_valid_after(datetime.now(UTC) - timedelta(days=10))
        .sign(ca_key, hashes.SHA256())
    )
    expired_pem = expired_signer_cert.public_bytes(serialization.Encoding.PEM)

    with pytest.raises(ValidationError) as exc:
        load_signing_material(
            certificate=ContentFile(expired_pem),
            private_key_data=test_certs['signer_key_pem'].decode(),
            password='',
            wwdr_certificate=ContentFile(test_certs['ca_pem']),
        )
    assert 'expired or not yet valid' in str(exc.value)


def test_expired_wwdr_certificate_raises_validation_error(test_certs):
    expired_ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    expired_ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Expired WWDR')])
    expired_ca_cert = (
        x509.CertificateBuilder()
        .subject_name(expired_ca_name)
        .issuer_name(expired_ca_name)
        .public_key(expired_ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=200))
        .not_valid_after(datetime.now(UTC) - timedelta(days=20))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(expired_ca_key, hashes.SHA256())
    )
    expired_ca_pem = expired_ca_cert.public_bytes(serialization.Encoding.PEM)

    with pytest.raises(ValidationError) as exc:
        load_signing_material(
            certificate=ContentFile(test_certs['signer_pem']),
            private_key_data=test_certs['signer_key_pem'].decode(),
            password='',
            wwdr_certificate=ContentFile(expired_ca_pem),
        )
    assert 'Apple WWDR CA certificate is expired or not yet valid' in str(exc.value)


def test_sign_manifest_contains_signing_time(test_certs):
    material = load_signing_material(
        certificate=ContentFile(test_certs['signer_pem']),
        private_key_data=test_certs['signer_key_pem'].decode(),
        password='',
        wwdr_certificate=ContentFile(test_certs['ca_pem']),
    )
    manifest_data = json.dumps({'pass.json': '1234567890abcdef'}).encode('utf-8')
    sig = sign_manifest(manifest_data, material)
    assert isinstance(sig, bytes)
    assert len(sig) > 100

    signing_time_oid_der = b'\x2a\x86\x48\x86\xf7\x0d\x01\t\x05'
    assert signing_time_oid_der in sig


@pytest.mark.django_db
def test_pass_data_structure(env):
    o, event, order, pos = env
    with scope(organizer=o, event=event):
        event.settings.set('ticketoutput_passbook_team_id', 'TEAM123456')
        event.settings.set('ticketoutput_passbook_pass_type_id', 'pass.eventyay.ticket')
        event.settings.set('ticketoutput_passbook_background_color', '#1b4d6b')
        event.settings.set('ticketoutput_passbook_foreground_color', '#ffffff')
        event.settings.set('ticketoutput_passbook_label_color', '#e0e0e0')
        event.geo_lat = Decimal('37.7749')
        event.geo_lon = Decimal('-122.4194')
        event.save()

        output = PassbookTicketOutput(event)
        data = output.pass_data(pos)

        assert data['formatVersion'] == 1
        assert data['passTypeIdentifier'] == 'pass.eventyay.ticket'
        assert data['teamIdentifier'] == 'TEAM123456'
        assert data['serialNumber'] == f'{event.organizer.slug}-{event.slug}-{order.code}-{pos.positionid}'
        assert data['organizationName'] == str(event.organizer.name)
        assert data['description'] == f'Ticket for {event.name}'
        assert data['backgroundColor'] == 'rgb(27, 77, 107)'
        assert data['foregroundColor'] == 'rgb(255, 255, 255)'
        assert data['labelColor'] == 'rgb(224, 224, 224)'

        # Check locations geo-coordinates
        assert 'locations' in data
        assert data['locations'][0]['latitude'] == pytest.approx(37.7749)
        assert data['locations'][0]['longitude'] == pytest.approx(-122.4194)

        event_ticket = data['eventTicket']
        assert 'primaryFields' in event_ticket
        assert 'secondaryFields' in event_ticket
        assert 'auxiliaryFields' in event_ticket
        assert 'backFields' in event_ticket

        assert data['barcode']['message'] == pos.secret
        assert data['barcode']['format'] == 'PKBarcodeFormatQR'
        assert data['barcodes'][0]['message'] == pos.secret
        assert data['relevantDate'].endswith('Z')
        assert data['expirationDate'].endswith('Z')


@pytest.mark.django_db
def test_pass_files_and_generate(env, test_certs):
    o, event, order, pos = env
    with scope(organizer=o, event=event):
        cert_path = default_storage.save('pub/test_cert_gen.pem', ContentFile(test_certs['signer_pem']))
        wwdr_path = default_storage.save('pub/test_wwdr_gen.pem', ContentFile(test_certs['ca_pem']))
        event.settings.set('ticketoutput_passbook_team_id', 'TEAM123456')
        event.settings.set('ticketoutput_passbook_pass_type_id', 'pass.eventyay.ticket')
        event.settings.set('ticketoutput_passbook_certificate', f'file://{cert_path}')
        event.settings.set('ticketoutput_passbook_private_key', test_certs['signer_key_pem'].decode())
        event.settings.set('ticketoutput_passbook_wwdr_certificate', f'file://{wwdr_path}')

        output = PassbookTicketOutput(event)
        files = output.pass_files(pos)

        assert 'pass.json' in files
        assert 'icon.png' in files
        assert 'icon@2x.png' in files
        assert 'icon@3x.png' in files
        assert 'logo.png' in files
        assert 'logo@2x.png' in files
        assert 'logo@3x.png' in files

        filename, mimetype, content = output.generate(pos)
        assert filename == f'{event.slug}-{order.code}-{pos.positionid}.pkpass'
        assert mimetype == 'application/vnd.apple.pkpass'

        zip_buf = BytesIO(content)
        assert zipfile.is_zipfile(zip_buf)
        with zipfile.ZipFile(zip_buf, 'r') as zf:
            namelist = zf.namelist()
            assert 'pass.json' in namelist
            assert 'manifest.json' in namelist
            assert 'signature' in namelist
            assert 'icon.png' in namelist
            assert 'logo.png' in namelist

            manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
            assert 'pass.json' in manifest
            assert 'icon.png' in manifest
            assert 'logo.png' in manifest


def test_form_fields_validation(test_certs):
    cert_field = CertificateFileField()

    valid_file = SimpleUploadedFile('cert.pem', test_certs['signer_pem'], content_type='application/x-pem-file')
    cleaned_cert = cert_field.clean(valid_file)
    assert isinstance(cleaned_cert, SimpleUploadedFile)
    assert cleaned_cert.read().startswith(b'-----BEGIN CERTIFICATE-----')

    invalid_file = SimpleUploadedFile('invalid.txt', b'NOT A VALID CERTIFICATE', content_type='text/plain')
    with pytest.raises(ValidationError):
        cert_field.clean(invalid_file)

    png_field = PNGImageField()
    blank_png = create_blank_png(10, 10)
    valid_png = SimpleUploadedFile('icon.png', blank_png, content_type='image/png')
    cleaned_png = png_field.clean(valid_png)
    assert cleaned_png is not None

    widget = PrivateKeyWidget()
    ctx = widget.get_context('key', 'SECRET_KEY_DATA', {})
    assert ctx['widget']['value'] == '*****'


@pytest.mark.django_db
def test_settings_form_clean(env, test_certs):
    o, event, order, pos = env
    with scope(organizer=o, event=event):
        output = PassbookTicketOutput(event)
        cert_file = SimpleUploadedFile('cert.pem', test_certs['signer_pem'])
        wwdr_file = SimpleUploadedFile('wwdr.pem', test_certs['ca_pem'])

        cleaned = output.settings_form_clean({
            'ticketoutput_passbook__enabled': True,
            'ticketoutput_passbook_team_identifier': 'TEAM123456',
            'ticketoutput_passbook_pass_type_identifier': 'pass.eventyay.ticket',
            'ticketoutput_passbook_certificate': cert_file,
            'ticketoutput_passbook_private_key': test_certs['signer_key_pem'].decode(),
            'ticketoutput_passbook_private_key_password': '',
            'ticketoutput_passbook_wwdr_certificate': wwdr_file,
        })
        assert cleaned['ticketoutput_passbook__enabled'] is True

        # Validation error when credentials do not match
        with pytest.raises(ValidationError):
            output.settings_form_clean({
                'ticketoutput_passbook__enabled': True,
                'ticketoutput_passbook_team_identifier': 'WRONG_TEAM',
                'ticketoutput_passbook_pass_type_identifier': 'pass.eventyay.ticket',
                'ticketoutput_passbook_certificate': cert_file,
                'ticketoutput_passbook_private_key': test_certs['signer_key_pem'].decode(),
                'ticketoutput_passbook_private_key_password': '',
                'ticketoutput_passbook_wwdr_certificate': wwdr_file,
            })


def test_read_file_handling():
    # Empty / None
    assert read_file(None) == b''
    assert read_file('') == b''

    # Raw bytes
    assert read_file(b'binary data') == b'binary data'

    # String with PEM content
    assert read_file('-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----') == (
        b'-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----'
    )

    # File-like BytesIO
    buf = BytesIO(b'in-memory file')
    assert read_file(buf) == b'in-memory file'
    assert buf.tell() == 0

    # Non-existent storage file returns empty bytes without crashing
    assert read_file('file://non_existent_file_path_12345.pem') == b''


@pytest.mark.django_db
def test_combined_download_exclusion(env, test_certs):
    o, event, order, pos = env
    with scope(organizer=o, event=event):
        cert_path = default_storage.save('pub/test_cert_comb.pem', ContentFile(test_certs['signer_pem']))
        wwdr_path = default_storage.save('pub/test_wwdr_comb.pem', ContentFile(test_certs['ca_pem']))
        event.settings.set('ticketoutput_passbook_team_identifier', 'TEAM123456')
        event.settings.set('ticketoutput_passbook_pass_type_identifier', 'pass.eventyay.ticket')
        event.settings.set('ticketoutput_passbook_certificate', f'file://{cert_path}')
        event.settings.set('ticketoutput_passbook_private_key', test_certs['signer_key_pem'].decode())
        event.settings.set('ticketoutput_passbook_wwdr_certificate', f'file://{wwdr_path}')
        event.settings.set('ticketoutput_passbook__enabled', True)

        output = PassbookTicketOutput(event)
        assert output.is_enabled is True
        assert output.multi_download_enabled is False

        # 1. Check OrderDownloadsField excludes passbook from combined order downloads
        factory = APIRequestFactory()
        request = factory.get('/')
        downloads_field = OrderDownloadsField()
        downloads_field._context = {'request': request}
        downloads = downloads_field.to_representation(order)
        passbook_downloads = [d for d in downloads if d['output'] == 'passbook']
        assert len(passbook_downloads) == 0

        # 2. Check get_combined_ticket_output_identifier excludes passbook
        combined_id = get_combined_ticket_output_identifier(event)
        assert combined_id != 'passbook'
