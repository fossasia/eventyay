import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.api.serializers.event import CloneEventSerializer
from eventyay.base.models import Event, Team


@pytest.fixture
def clone_url(event):
    return reverse('eventyay_common:event.clone', kwargs={
        'organizer': event.organizer.slug,
        'event': event.slug
    })


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_clone_view_get(organizer_client, event, clone_url):
    response = organizer_client.get(clone_url)
    assert response.status_code == 200
    assert 'form' in response.context


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_clone_view_post_success(organizer_client, event, clone_url, user, team):
    with scopes_disabled():
        event.live = True
        event.tickets_published = True
        event.talks_published = True
        event.testmode = True
        event.save()
        tr = event.tax_rules.create(rate=19, name='VAT')
        event.products.create(
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
        'clone_settings': 'on',
        'clone_design_texts': 'on',
        'clone_email_settings': 'on',
        'clone_products': 'on',
        'clone_questions': 'on',
        'clone_checkin_lists': 'on',
        'clone_payment_settings': 'on',
    }

    response = organizer_client.post(clone_url, payload, follow=True)
    assert response.status_code == 200, response.content

    cloned_event = Event.objects.get(slug='cloned-event')

    assert str(cloned_event.name) == 'Cloned Event'
    assert cloned_event.organizer == event.organizer
    assert cloned_event.settings.timezone == 'Europe/Berlin'
    assert cloned_event.live is False
    assert cloned_event.tickets_published is False
    assert cloned_event.talks_published is False
    assert cloned_event.testmode is False
    assert cloned_event.private_testmode is False

    assert team.all_events or Team.objects.filter(limit_events=cloned_event, members=user).exists()

    with scopes_disabled():
        assert cloned_event.tax_rules.filter(rate=Decimal('19.00')).count() == 1
        assert cloned_event.products.count() == 1
        assert cloned_event.products.first().name == 'Early-bird ticket'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_clone_view_post_selective_clone(organizer_client, event, clone_url):
    with scopes_disabled():
        event.live = True
        event.tickets_published = True
        event.talks_published = True
        event.testmode = True
        event.save()
        tr = event.tax_rules.create(rate=19, name='VAT')
        event.products.create(
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

    cloned_event = Event.objects.get(slug='cloned-event-2')

    assert str(cloned_event.name) == 'Cloned Event 2'
    assert cloned_event.live is False
    assert cloned_event.tickets_published is False
    assert cloned_event.talks_published is False
    assert cloned_event.testmode is False
    assert cloned_event.private_testmode is False

    with scopes_disabled():
        # Products and tax rules should not be cloned since clone_ticketing_data is not set
        assert cloned_event.tax_rules.count() == 0
        assert cloned_event.products.count() == 0


def _simulate_copy_data_from(self, other, clone_options=None):
    """Simulate copy_data_from copying testmode and publication state from source event."""
    self.testmode = other.testmode
    self.live = other.live
    self.tickets_published = other.tickets_published
    self.talks_published = other.talks_published
    self.private_testmode = other.private_testmode
    self.save()


@pytest.mark.django_db
def test_clone_event_serializer_preserves_explicit_testmode(event):
    with scopes_disabled():
        event.live = True
        event.tickets_published = True
        event.talks_published = True
        event.testmode = False
        event.save()

    data = {
        'name': {'en': 'API Cloned Event Testmode True'},
        'slug': 'api-clone-testmode-true',
        'date_from': '2028-12-27T10:00:00Z',
        'date_to': '2028-12-28T10:00:00Z',
        'currency': 'EUR',
        'locale': 'en',
        'locales': ['en'],
        'testmode': True,
    }
    with scopes_disabled(), patch.object(Event, 'copy_data_from', autospec=True, side_effect=_simulate_copy_data_from):
        request = SimpleNamespace(organizer=event.organizer)
        serializer = CloneEventSerializer(
            data=data,
            context={'request': request, 'organizer': event.organizer, 'event': event.slug},
        )
        assert serializer.is_valid(), serializer.errors
        cloned = serializer.save(organizer=event.organizer)
        cloned.refresh_from_db()

        assert cloned.testmode is True
        assert cloned.live is False
        assert cloned.tickets_published is False
        assert cloned.talks_published is False
        assert cloned.private_testmode is False


@pytest.mark.django_db
def test_clone_event_serializer_resets_testmode_when_omitted(event):
    with scopes_disabled():
        event.live = True
        event.tickets_published = True
        event.talks_published = True
        event.testmode = True
        event.save()

    data = {
        'name': {'en': 'API Cloned Event Testmode Omitted'},
        'slug': 'api-clone-testmode-omitted',
        'date_from': '2028-12-27T10:00:00Z',
        'date_to': '2028-12-28T10:00:00Z',
        'currency': 'EUR',
        'locale': 'en',
        'locales': ['en'],
    }
    with scopes_disabled(), patch.object(Event, 'copy_data_from', autospec=True, side_effect=_simulate_copy_data_from):
        request = SimpleNamespace(organizer=event.organizer)
        serializer = CloneEventSerializer(
            data=data,
            context={'request': request, 'organizer': event.organizer, 'event': event.slug},
        )
        assert serializer.is_valid(), serializer.errors
        cloned = serializer.save(organizer=event.organizer)
        cloned.refresh_from_db()

        assert cloned.testmode is False
        assert cloned.live is False
        assert cloned.tickets_published is False
        assert cloned.talks_published is False
        assert cloned.private_testmode is False
