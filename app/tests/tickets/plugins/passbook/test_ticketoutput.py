import hashlib
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from eventyay.plugins.passbook.forms import CertificateFileField
from eventyay.plugins.passbook.ticketoutput import PassbookTicketOutput, load_signing_material


class FakeSettings:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None, as_type=str, **kwargs):
        return self.values.get(key, default)


def certificate(common_name, key, issuer_certificate=None, issuer_key=None, team=None, pass_type=None):
    now = datetime.now(UTC)
    subject_attributes = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    if team:
        subject_attributes.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, team))
    if pass_type:
        subject_attributes.append(x509.NameAttribute(NameOID.USER_ID, pass_type))
    subject = x509.Name(subject_attributes)
    issuer = issuer_certificate.subject if issuer_certificate else subject
    signer = issuer_key or key
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=issuer_certificate is None, path_length=None), critical=True)
        .sign(signer, hashes.SHA256())
    )


@pytest.fixture
def signing_credentials():
    wwdr_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wwdr_certificate = certificate('WWDR', wwdr_key)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_certificate = certificate(
        'Pass',
        signing_key,
        wwdr_certificate,
        wwdr_key,
        team='TEAM123',
        pass_type='pass.org.eventyay.test',
    )
    return {
        'certificate': ContentFile(
            signing_certificate.public_bytes(serialization.Encoding.PEM),
            name='certificate.pem',
        ),
        'private_key': signing_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        'wwdr_certificate': ContentFile(
            wwdr_certificate.public_bytes(serialization.Encoding.PEM),
            name='wwdr.pem',
        ),
        'signing_certificate': signing_certificate,
        'wwdr': wwdr_certificate,
    }


def output_for(signing_credentials):
    values = {
        'ticketoutput_passbook__enabled': True,
        'ticketoutput_passbook_team_identifier': 'TEAM123',
        'ticketoutput_passbook_pass_type_identifier': 'pass.org.eventyay.test',
        'ticketoutput_passbook_certificate': signing_credentials['certificate'],
        'ticketoutput_passbook_private_key': signing_credentials['private_key'],
        'ticketoutput_passbook_private_key_password': '',
        'ticketoutput_passbook_wwdr_certificate': signing_credentials['wwdr_certificate'],
    }
    organizer = SimpleNamespace(slug='eventyay', name='eventyay')
    event = SimpleNamespace(
        settings=FakeSettings(values),
        organizer=organizer,
        slug='conference',
        name='Conference',
        date_from=datetime(2026, 11, 1, 9, tzinfo=UTC),
        date_to=datetime(2026, 11, 1, 18, tzinfo=UTC),
        geo_lat=52.52,
        geo_lon=13.405,
    )
    return PassbookTicketOutput(event), event


def test_load_signing_material_rejects_mismatched_key(signing_credentials):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = other_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    with pytest.raises(ValidationError, match='does not match'):
        load_signing_material(
            signing_credentials['certificate'],
            private_key,
            '',
            signing_credentials['wwdr_certificate'],
        )


def test_certificate_field_parses_der(signing_credentials):
    certificate_bytes = signing_credentials['signing_certificate'].public_bytes(serialization.Encoding.DER)

    result = CertificateFileField().clean(SimpleUploadedFile('certificate.cer', certificate_bytes))

    assert result.read().startswith(b'-----BEGIN CERTIFICATE-----')


def test_certificate_field_rejects_invalid_data():
    with pytest.raises(ValidationError, match='valid X.509'):
        CertificateFileField().clean(SimpleUploadedFile('certificate.pem', b'not-a-certificate'))


def test_generate_signed_pkpass(signing_credentials, monkeypatch):
    output, event = output_for(signing_credentials)
    order = SimpleNamespace(event=event, code='ABC12')
    position = SimpleNamespace(
        order=order,
        subevent=None,
        product=SimpleNamespace(name='Standard'),
        variation=None,
        seat=None,
        attendee_name='Ada Lovelace',
        secret='ticket-secret',
        positionid=1,
    )
    monkeypatch.setattr(
        'eventyay.plugins.passbook.ticketoutput.build_absolute_uri',
        lambda *args, **kwargs: 'https://example.com/conference/',
    )

    filename, content_type, content = output.generate(position)

    assert filename == 'conference-ABC12-1.pkpass'
    assert content_type == 'application/vnd.apple.pkpass'
    with ZipFile(BytesIO(content)) as archive:
        assert set(archive.namelist()) == {
            'icon.png',
            'icon@2x.png',
            'icon@3x.png',
            'manifest.json',
            'pass.json',
            'signature',
        }
        pass_data = json.loads(archive.read('pass.json'))
        assert pass_data['barcodes'][0]['message'] == 'ticket-secret'
        assert pass_data['eventTicket']['primaryFields'][0]['value'] == 'Conference'
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['pass.json'] == hashlib.sha1(archive.read('pass.json')).hexdigest()
        certificates = pkcs7.load_der_pkcs7_certificates(archive.read('signature'))
        assert signing_credentials['signing_certificate'] in certificates
        assert signing_credentials['wwdr'] in certificates


def test_output_is_hidden_without_credentials(signing_credentials):
    output, event = output_for(signing_credentials)
    event.settings.values['ticketoutput_passbook_wwdr_certificate'] = None

    assert output.is_enabled is False
    assert output.preview_allowed is False
