import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.signals import register_data_exporters


@pytest.fixture
def event_without_reports_plugin():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy-reports')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy-reports',
        date_from=now(),
        # Intentionally omit eventyay.plugins.reports — it must still work.
        plugins='eventyay.plugins.banktransfer',
    )
    user = User.objects.create_user('reports@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_view_orders=True, can_change_orders=True)
    team.members.add(user)
    team.limit_events.add(event)
    return event, user


@pytest.mark.django_db
def test_reports_plugin_is_hidden_from_event_available_plugins(event_without_reports_plugin):
    event, _user = event_without_reports_plugin
    with scope(event=event):
        assert 'eventyay.plugins.reports' not in event.available_plugins
        assert 'eventyay.plugins.checkinlists' not in event.available_plugins


@pytest.mark.django_db
def test_pdfreport_exporter_registers_without_plugin_enabled(event_without_reports_plugin):
    event, _user = event_without_reports_plugin
    with scope(event=event):
        identifiers = [response(event).identifier for _receiver, response in register_data_exporters.send(event)]
    assert 'pdfreport' in identifiers
    assert 'ordertaxes' in identifiers
    assert 'ordertaxeslist' in identifiers


@pytest.mark.django_db
def test_orders_export_page_shows_pdfreport_without_plugin_enabled(client, event_without_reports_plugin):
    event, user = event_without_reports_plugin
    assert client.login(email='reports@dummy.dummy', password='dummy')
    url = f'/control/event/{event.organizer.slug}/{event.slug}/orders/export/'
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Data export' in content
    assert 'pdfreport' in content

    filtered = client.get(f'{url}?identifier=pdfreport')
    assert filtered.status_code == 200
    filtered_content = filtered.content.decode()
    assert 'pdfreport' in filtered_content
    assert 'No export matching this request is available.' not in filtered_content

@pytest.mark.django_db
def test_orders_export_page_shows_empty_state_for_unknown_identifier(client, event_without_reports_plugin):
    event, user = event_without_reports_plugin
    assert client.login(email='reports@dummy.dummy', password='dummy')
    url = f'/control/event/{event.organizer.slug}/{event.slug}/orders/export/'
    
    filtered = client.get(f'{url}?identifier=unknown_exporter_123')
    assert filtered.status_code == 200
    filtered_content = filtered.content.decode()
    assert 'No export matching this request is available.' in filtered_content
    assert 'Show all available exports' in filtered_content
