import pytest
from bs4 import BeautifulSoup
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User


@pytest.fixture
def env():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    t = Team.objects.create(
        organizer=event.organizer,
        can_view_orders=True,
        can_change_orders=True,
        can_manage_bank_transfers=True,
    )
    t.members.add(user)
    t.limit_events.add(event)
    return event, user


@pytest.mark.django_db
def test_import_csv_file(client, env):
    client.login(email='dummy@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import/')
    assert r.status_code == 200

    file = SimpleUploadedFile(
        'file.csv',
        """First name,Last name,Email
Dieter,Schneider,schneider@example.org
Daniel,Wulf,daniel@example.org
Daniel,Wulf,daniel@example.org
Anke,Müller,anke@example.net

""".encode('utf-8'),
        content_type='text/csv',
    )

    r = client.post('/control/event/dummy/dummy/orders/import/', {'file': file}, follow=True)
    doc = BeautifulSoup(r.content, 'lxml')
    assert doc.select('select[name=orders]')
    assert doc.select('select[name=status]')
    assert doc.select('select[name=attendee_email]')
    assert b'Dieter' in r.content
    assert b'daniel@example.org' in r.content
    assert b'Anke' not in r.content


@pytest.mark.django_db
def test_import_export_page_loads(client, env):
    client.login(email='dummy@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/')
    assert r.status_code == 200
    assert b'Import / Export' in r.content
    assert b'Export data' in r.content
    assert b'Import attendees' in r.content
    assert b'Import bank transfers' in r.content
    assert b'Export bank transfer refunds' in r.content
    assert b'pretixcontrol/css/import-export.css' in r.content
    assert b'pretixcontrol/js/ui/import_export.js' in r.content


@pytest.mark.django_db
def test_import_export_page_specific_identifier_hides_banktransfer_refunds(client, env):
    client.login(email='dummy@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/?identifier=invoices')
    assert r.status_code == 200
    assert b'Export bank transfer refunds' not in r.content


@pytest.mark.django_db
def test_import_export_banktransfer_only_permission(client):
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('bt@dummy.dummy', 'dummy')
    t = Team.objects.create(
        organizer=event.organizer,
        can_manage_bank_transfers=True,
    )
    t.members.add(user)
    t.limit_events.add(event)

    client.login(email='bt@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/')
    assert r.status_code == 200
    assert b'Import / Export' in r.content
    assert b'Import bank transfers' in r.content
    assert b'Export data' not in r.content
    assert b'Import attendees' not in r.content

    # Visiting banktransfer endpoint redirects to unified tab and succeeds
    r_redirect = client.get('/control/event/dummy/dummy/plugins/banktransfer/', follow=True)
    assert r_redirect.status_code == 200
    assert b'Import bank transfers' in r_redirect.content


@pytest.mark.django_db
def test_import_export_change_orders_only_permission(client):
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('change@dummy.dummy', 'dummy')
    t = Team.objects.create(
        organizer=event.organizer,
        can_change_orders=True,
    )
    t.members.add(user)
    t.limit_events.add(event)

    client.login(email='change@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/')
    assert r.status_code == 200
    assert b'Import attendees' in r.content
    assert b'Export data' not in r.content
    assert b'Import bank transfers' not in r.content


@pytest.mark.django_db
def test_import_export_view_orders_only_permission(client):
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('view@dummy.dummy', 'dummy')
    t = Team.objects.create(
        organizer=event.organizer,
        can_view_orders=True,
    )
    t.members.add(user)
    t.limit_events.add(event)

    client.login(email='view@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/')
    assert r.status_code == 200
    assert b'Export data' in r.content
    assert b'Import attendees' not in r.content
    assert b'Import bank transfers' not in r.content


@pytest.mark.django_db
def test_import_export_no_permission_denied(client):
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('none@dummy.dummy', 'dummy')
    t = Team.objects.create(
        organizer=event.organizer,
        can_view_vouchers=True,
    )
    t.members.add(user)
    t.limit_events.add(event)

    client.login(email='none@dummy.dummy', password='dummy')
    r = client.get('/control/event/dummy/dummy/orders/import-export/')
    assert r.status_code == 403



