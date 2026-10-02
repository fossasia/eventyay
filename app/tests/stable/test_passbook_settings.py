from collections import OrderedDict
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile

from eventyay.base.forms import SECRET_REDACTED
from eventyay.control.forms.event import ProviderForm
from eventyay.plugins.passbook.ticketoutput import PassbookTicketOutput


def create_certificate(common_name, key, issuer_certificate=None, issuer_key=None, team=None, pass_type=None):
    now = datetime.now(UTC)
    subject_attributes = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    if team:
        subject_attributes.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, team))
    if pass_type:
        subject_attributes.append(x509.NameAttribute(NameOID.USER_ID, pass_type))
    subject = x509.Name(subject_attributes)
    issuer = issuer_certificate.subject if issuer_certificate else subject
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=issuer_certificate is None, path_length=None), critical=True)
        .sign(issuer_key or key, hashes.SHA256())
    )


def signing_credentials():
    wwdr_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wwdr_certificate = create_certificate('WWDR', wwdr_key)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_certificate = create_certificate(
        'Pass',
        signing_key,
        wwdr_certificate,
        wwdr_key,
        team='TEAM123',
        pass_type='pass.org.eventyay.test',
    )
    return {
        'certificate': signing_certificate.public_bytes(serialization.Encoding.PEM),
        'private_key': signing_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        'wwdr_certificate': wwdr_certificate.public_bytes(serialization.Encoding.PEM),
    }


def passbook_form(event, data, files=None):
    provider = PassbookTicketOutput(event)
    form = ProviderForm(
        obj=event,
        settingspref='ticketoutput_passbook_',
        provider=provider,
        data=data,
        files=files,
    )
    form.fields = OrderedDict(
        [(f'ticketoutput_passbook_{key}', field) for key, field in provider.settings_form_fields.items()]
    )
    form.prepare_fields()
    return form


@pytest.mark.django_db
def test_passbook_settings_files_remain_binary_after_second_save(event):
    credentials = signing_credentials()
    data = {
        'ticketoutput_passbook__enabled': 'on',
        'ticketoutput_passbook_team_identifier': 'TEAM123',
        'ticketoutput_passbook_pass_type_identifier': 'pass.org.eventyay.test',
        'ticketoutput_passbook_private_key': credentials['private_key'],
        'ticketoutput_passbook_private_key_password': '',
    }
    files = {
        'ticketoutput_passbook_certificate': SimpleUploadedFile(
            'certificate.pem', credentials['certificate'], 'application/x-pem-file'
        ),
        'ticketoutput_passbook_wwdr_certificate': SimpleUploadedFile(
            'wwdr.pem', credentials['wwdr_certificate'], 'application/x-pem-file'
        ),
    }
    form = passbook_form(event, data, files)
    assert form.is_valid(), form.errors.as_json()
    form.save()
    event.settings.flush()

    stored_certificate = event.settings.get('ticketoutput_passbook_certificate', as_type=File, binary_file=True)
    assert isinstance(stored_certificate.read(), bytes)
    stored_certificate.close()
    assert PassbookTicketOutput(event).is_available is True
    assert PassbookTicketOutput(event).signing_material.certificate is not None

    second_data = {
        **data,
        'ticketoutput_passbook_private_key': SECRET_REDACTED,
    }
    second_form = passbook_form(event, second_data)
    assert second_form.is_valid(), second_form.errors.as_json()
    second_form.save()
    event.settings.flush()
    assert PassbookTicketOutput(event).signing_material.certificate is not None


@pytest.mark.django_db
def test_passbook_is_disabled_by_default(event):
    event.set_defaults()
    assert event.settings.get('ticketoutput_passbook__enabled', as_type=bool) is False
