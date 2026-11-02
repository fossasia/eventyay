import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer


PRESALE_START = datetime.datetime(2099, 5, 1, 8, 30, tzinfo=ZoneInfo('UTC'))


@pytest.fixture
@scopes_disabled()
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now() + datetime.timedelta(days=365 * 80),
        presale_start=PRESALE_START,
        live=True,
        tickets_published=True,
    )
    event.settings.timezone = 'Europe/Berlin'
    return event


@pytest.mark.django_db
def test_widget_shows_presale_start_in_event_timezone(client, event):
    response = client.get('/dummy/dummy/widget/product_list')
    assert response.status_code == 200
    # 08:30 UTC is 10:30 in Berlin (summer time).
    assert response.json()['error'] == 'The presale for this event will start on 2099-05-01 at 10:30.'


@pytest.mark.django_db
def test_organizer_event_list_shows_presale_start_in_event_timezone(client, event):
    event.presale_start = datetime.datetime(2099, 5, 1, 20, 0, tzinfo=ZoneInfo('UTC'))
    event.save()
    event.settings.timezone = 'Asia/Tokyo'

    response = client.get('/dummy/widget/product_list')

    assert response.status_code == 200
    # 20:00 UTC is 05:00 on the next day in Tokyo.
    assert response.json()['events'][0]['availability'] == {
        'color': 'orange',
        'text': 'from 2099-05-02',
        'reason': 'soon',
    }
