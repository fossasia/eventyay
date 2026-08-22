import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Team


@pytest.fixture
def clone_url(event):
    return reverse('eventyay_common:event.clone', kwargs={
        'organizer': event.organizer.slug,
        'event': event.slug
    })


@pytest.mark.django_db
def test_clone_view_get(organizer_client, event, clone_url):
    response = organizer_client.get(clone_url)
    assert response.status_code == 200
    assert 'form' in response.context


@pytest.mark.django_db
def test_clone_view_post_success(organizer_client, event, clone_url, user):
    with scopes_disabled():
        tr = event.tax_rules.create(rate=19, name='VAT')
        event.items.create(
            name='Early-bird ticket',
            category=None,
            default_price=23,
            tax_rule=tr,
            admission=True,
        )
        event.settings.tax_rate_default = tr

    berlin_tz = ZoneInfo('Europe/Berlin')
    start_date = datetime.datetime(2028, 12, 26, 9, 0, 0, tzinfo=berlin_tz)
    end_date = datetime.datetime(2028, 12, 30, 17, 0, 0, tzinfo=berlin_tz)

    payload = {
        'name_0': 'Cloned Event',
        'slug': 'cloned-event',
        'date_from_0': start_date.strftime('%Y-%m-%d'),
        'date_from_1': start_date.strftime('%H:%M'),
        'date_to_0': end_date.strftime('%Y-%m-%d'),
        'date_to_1': end_date.strftime('%H:%M'),
        'timezone': 'Europe/Berlin',
        'locale': 'en',
        'locales': ['en'],
        'clone_common_data': 'on',
        'clone_ticketing_data': 'on',
        'clone_talk_data': 'on',
        'clone_settings': 'on',
        'clone_design_texts': 'on',
        'clone_email_settings': 'on',
        'clone_products': 'on',
        'clone_questions': 'on',
        'clone_checkin_lists': 'on',
        'clone_payment_settings': 'on',
        'clone_cfp': 'on',
        'clone_session_types_tracks': 'on',
        'clone_review_settings': 'on',
    }

    response = organizer_client.post(clone_url, payload, follow=True)
    assert response.status_code == 200, response.content

    from eventyay.base.models import Event
    cloned_event = Event.objects.get(slug='cloned-event')

    assert cloned_event.name == 'Cloned Event'
    assert cloned_event.organizer == event.organizer
    assert cloned_event.settings.timezone == 'Europe/Berlin'
    
    assert Team.objects.filter(limit_events=cloned_event, members=user).exists()
    
    with scopes_disabled():
        assert cloned_event.tax_rules.filter(rate=Decimal('19.00')).count() == 1
        assert cloned_event.items.count() == 1
        assert cloned_event.items.first().name == 'Early-bird ticket'


@pytest.mark.django_db
def test_clone_view_post_selective_clone(organizer_client, event, clone_url):
    with scopes_disabled():
        tr = event.tax_rules.create(rate=19, name='VAT')
        event.items.create(
            name='Early-bird ticket',
            category=None,
            default_price=23,
            tax_rule=tr,
            admission=True,
        )

    berlin_tz = ZoneInfo('Europe/Berlin')
    start_date = datetime.datetime(2028, 12, 26, 9, 0, 0, tzinfo=berlin_tz)
    end_date = datetime.datetime(2028, 12, 30, 17, 0, 0, tzinfo=berlin_tz)

    payload = {
        'name_0': 'Cloned Event 2',
        'slug': 'cloned-event-2',
        'date_from_0': start_date.strftime('%Y-%m-%d'),
        'date_from_1': start_date.strftime('%H:%M'),
        'date_to_0': end_date.strftime('%Y-%m-%d'),
        'date_to_1': end_date.strftime('%H:%M'),
        'timezone': 'Europe/Berlin',
        'locale': 'en',
        'locales': ['en'],
        # Disable ticketing and talk data cloning
        'clone_common_data': 'on',
        'clone_settings': 'on',
        'clone_design_texts': 'on',
        'clone_email_settings': 'on',
    }

    response = organizer_client.post(clone_url, payload, follow=True)
    assert response.status_code == 200, response.content

    from eventyay.base.models import Event
    cloned_event = Event.objects.get(slug='cloned-event-2')

    assert cloned_event.name == 'Cloned Event 2'
    
    with scopes_disabled():
        # Items and tax rules should not be cloned since clone_ticketing_data is not set
        assert cloned_event.tax_rules.count() == 0
        assert cloned_event.items.count() == 0
