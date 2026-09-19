import json
import subprocess
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    ProductVariation,
    Team,
    User,
)
from eventyay.base.signals import register_ticket_outputs
from eventyay.plugins.passbook.passbook import PassbookOutput


@pytest.fixture
def passbook_env():
    o = Organizer.objects.create(name='Dummy Org', slug='dummy-org')
    event = Event.objects.create(
        organizer=o,
        name='Passbook Test Event',
        slug='passbook-event',
        date_from=now(),
        date_to=now() + timedelta(days=1),
        live=True,
        plugins='eventyay.plugins.passbook',
    )
    order = Order.objects.create(
        code='PASS1',
        event=event,
        email='attendee@example.com',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('25.00'),
    )
    product = Product.objects.create(event=event, name='VIP Ticket', default_price=25)
    variation = ProductVariation.objects.create(product=product, default_price=25, value='Gold')
    pos = OrderPosition.objects.create(
        order=order,
        product=product,
        variation=variation,
        price=Decimal('25.00'),
        attendee_name_cached='Alice Smith',
        attendee_name_parts={'full_name': 'Alice Smith'},
        secret='TICKET_SECRET_98765',
    )
    return event, order, pos


@pytest.mark.django_db
def test_plugin_signal_registration(passbook_env):
    event, _, _ = passbook_env
    with scope(organizer=event.organizer):
        responses = register_ticket_outputs.send(event)
        output_classes = [resp for _, resp in responses]
        assert PassbookOutput in output_classes


def test_plugin_metadata():
    from django.apps import apps

    app = apps.get_app_config('passbook')
    assert app.verbose_name == 'Passbook Tickets'
    assert hasattr(app, 'EventyayPluginMeta')
    meta = app.EventyayPluginMeta
    assert meta.category == 'FORMAT'
    assert meta.featured is True


@pytest.mark.django_db
def test_passbook_output_properties_and_fields(passbook_env):
    event, _, _ = passbook_env
    with scope(organizer=event.organizer):
        output = PassbookOutput(event)
        assert output.identifier == 'passbook'
        assert output.multi_download_enabled is False
        assert output.download_button_icon == 'fa-mobile'

        fields = output.settings_form_fields
        assert 'selfscale' in fields
        assert 'icon' in fields
        assert 'logo' in fields
        assert 'background' in fields
        assert 'bg_color' in fields
        assert 'fg_color' in fields
        assert 'label_color' in fields
        assert 'latitude' in fields
        assert 'longitude' in fields


@pytest.mark.django_db
def test_event_default_passbook_enabled(passbook_env):
    event, _, _ = passbook_env
    with scope(organizer=event.organizer):
        event.set_defaults()
        assert event.settings.get('ticketoutput_passbook__enabled', as_type=bool) is True


@pytest.mark.django_db
def test_passbook_preview_allowed_requires_certs(passbook_env):
    event, _, _ = passbook_env
    with scope(organizer=event.organizer):
        output = PassbookOutput(event)
        assert output.preview_allowed is False

        from django.core.files.storage import default_storage

        cert_path = default_storage.save('test_cert.pem', ContentFile(b'fake-cert'))
        event.settings.set('passbook_certificate_file', ContentFile(b'fake-cert', name=cert_path))
        event.settings.set('passbook_key', 'fake-key')
        assert output.preview_allowed is True


@pytest.mark.django_db
def test_passbook_generate_without_certs_raises_validation_error(passbook_env):
    event, _, pos = passbook_env
    with scope(organizer=event.organizer):
        output = PassbookOutput(event)
        with pytest.raises(ValidationError):
            output.generate(pos)


@pytest.mark.django_db
def test_passbook_generate_pass_structure(passbook_env):
    event, order, pos = passbook_env
    with scope(organizer=event.organizer):
        event.settings.set('ticketoutput_passbook_bg_color', '#112233')
        event.settings.set('ticketoutput_passbook_fg_color', '#ffffff')
        event.settings.set('ticketoutput_passbook_label_color', '#aaaaaa')
        event.settings.set('ticketoutput_passbook_latitude', 37.7749)
        event.settings.set('ticketoutput_passbook_longitude', -122.4194)

        output = PassbookOutput(event)
        passfile = output.generate_pass(pos)

        assert passfile.backgroundColor == '#112233'
        assert passfile.foregroundColor == '#ffffff'
        assert passfile.labelColor == '#aaaaaa'
        assert passfile.barcode.message == 'TICKET_SECRET_98765'
        assert len(passfile.locations) == 1
        assert passfile.locations[0].latitude == 37.7749
        assert passfile.locations[0].longitude == -122.4194

        json_data = json.loads(passfile._createPassJson().decode('utf-8'))
        event_ticket = json_data['eventTicket']
        assert event_ticket['primaryFields'][0]['value'] == 'Passbook Test Event'
        assert 'VIP Ticket' in event_ticket['secondaryFields'][0]['value']


@pytest.mark.django_db
def test_passbook_full_generate_with_certs(passbook_env):
    event, order, pos = passbook_env
    with scope(organizer=event.organizer):
        with tempfile.TemporaryDirectory() as td:
            key_path = f'{td}/key.pem'
            cert_path = f'{td}/cert.pem'
            subprocess.run(
                [
                    'openssl',
                    'req',
                    '-new',
                    '-newkey',
                    'rsa:2048',
                    '-days',
                    '1',
                    '-nodes',
                    '-x509',
                    '-subj',
                    '/CN=TestPassbook',
                    '-keyout',
                    key_path,
                    '-out',
                    cert_path,
                ],
                check=True,
                capture_output=True,
            )

            with open(cert_path, 'rb') as f:
                cert_bytes = f.read()
            with open(key_path) as f:
                key_str = f.read()

            from django.core.files.storage import default_storage

            cert_name = default_storage.save('cert.pem', ContentFile(cert_bytes))
            ca_name = default_storage.save('ca.pem', ContentFile(cert_bytes))

            event.settings.set('passbook_certificate_file', ContentFile(cert_bytes, name=cert_name))
            event.settings.set('passbook_wwdr_certificate_file', ContentFile(cert_bytes, name=ca_name))
            event.settings.set('passbook_key', key_str)
            event.settings.set('passbook_team_id', 'TEST_TEAM')
            event.settings.set('passbook_pass_type_id', 'pass.org.eventyay.test')

            output = PassbookOutput(event)
            fname, ftype, pkpass_bytes = output.generate(pos)

            assert fname == f'{event.slug}-{order.code}.pkpass'
            assert ftype == 'application/vnd.apple.pkpass'
            assert len(pkpass_bytes) > 0

            # Inspect the generated .pkpass zip
            zf = zipfile.ZipFile(BytesIO(pkpass_bytes))
            namelist = zf.namelist()
            assert 'pass.json' in namelist
            assert 'manifest.json' in namelist
            assert 'signature' in namelist
            assert 'icon.png' in namelist
            assert 'logo.png' in namelist

            pass_json = json.loads(zf.read('pass.json').decode('utf-8'))
            assert pass_json['teamIdentifier'] == 'TEST_TEAM'
            assert pass_json['passTypeIdentifier'] == 'pass.org.eventyay.test'
            assert pass_json['barcode']['message'] == 'TICKET_SECRET_98765'
            assert pass_json['eventTicket']['primaryFields'][0]['value'] == 'Passbook Test Event'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_ticket_settings_view_passbook(passbook_env, client):
    event, _, _ = passbook_env
    user = User.objects.create_superuser('admin@example.com', 'adminpass')
    team = Team.objects.create(
        organizer=event.organizer,
        can_change_event_settings=True,
        can_view_orders=True,
    )
    team.members.add(user)
    team.limit_events.add(event)
    client.force_login(user)

    url = f'/control/event/{event.organizer.slug}/{event.slug}/settings/tickets'
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert 'Passbook Tickets' in content
    assert 'ticketoutput_passbook__enabled' in content
    assert 'ticketoutput_passbook_bg_color' in content
    assert 'ticketoutput_passbook_latitude' in content

    response = client.post(
        url,
        {
            'ticket_download': 'on',
            'ticket_secret_generator': 'random',
            'ticketoutput_passbook__enabled': 'on',
            'ticketoutput_passbook_bg_color': '#334455',
            'ticketoutput_passbook_fg_color': '#ffffff',
            'ticketoutput_passbook_label_color': '#cccccc',
            'ticketoutput_passbook_latitude': '52.5200',
            'ticketoutput_passbook_longitude': '13.4050',
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(organizer=event.organizer):
        event = Event.objects.get(pk=event.pk)
        assert event.settings.get('ticketoutput_passbook__enabled', as_type=bool) is True
        assert event.settings.get('ticketoutput_passbook_bg_color') == '#334455'
        assert event.settings.get('ticketoutput_passbook_latitude', as_type=float) == 52.52
