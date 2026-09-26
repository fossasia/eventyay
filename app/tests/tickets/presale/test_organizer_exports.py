import json
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer


FORMATS = ['schedule.json', 'schedule.xml', 'schedule.xcal']


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='MRMCD e.V.', slug='mrmcd')


@pytest.fixture
def env(organizer):
    event = Event.objects.create(
        organizer=organizer,
        name='MRMCD2015',
        slug='2015',
        date_from=now() + timedelta(days=10),
        live=True,
        is_public=True,
    )
    return organizer, event


@pytest.mark.django_db
@pytest.mark.parametrize('export_name', FORMATS)
def test_export_with_event_returns_200(env, client, export_name):
    r = client.get(f'/mrmcd/events/export/{export_name}/')
    assert r.status_code == 200
    if export_name == 'schedule.json':
        json.loads(r.content)
    else:
        ElementTree.fromstring(r.content)


@pytest.mark.django_db
@pytest.mark.parametrize('export_name', FORMATS)
def test_export_without_events_returns_200(organizer, client, export_name):
    r = client.get(f'/mrmcd/events/export/{export_name}/')
    assert r.status_code == 200
    if export_name == 'schedule.json':
        json.loads(r.content)
    else:
        ElementTree.fromstring(r.content)


@pytest.mark.django_db
def test_export_non_utc_timezone_converts_start_to_utc(organizer, client):
    start = datetime(now().year + 1, 6, 1, 9, 0, tzinfo=UTC)
    event = Event.objects.create(
        organizer=organizer,
        name='MRMCD2016',
        slug='2016',
        date_from=start,
        live=True,
        is_public=True,
    )
    with scopes_disabled():
        event.settings.timezone = 'America/New_York'

    r = client.get('/mrmcd/events/export/schedule.xcal/')
    assert r.status_code == 200
    assert f'{start:%Y%m%dT%H%M%S}Z' in r.content.decode()


@pytest.mark.django_db
def test_xcal_start_is_utc_when_organizer_has_timezone(organizer, client):
    start = datetime(now().year + 1, 6, 1, 9, 0, tzinfo=UTC)
    Event.objects.create(
        organizer=organizer,
        name='MRMCD2017',
        slug='2017',
        date_from=start,
        live=True,
        is_public=True,
    )
    organizer.settings.timezone = 'Europe/Berlin'

    r = client.get('/mrmcd/events/export/schedule.xcal/')
    assert r.status_code == 200
    assert f'<dtstart>{start:%Y%m%dT%H%M%S}Z</dtstart>' in r.content.decode()
