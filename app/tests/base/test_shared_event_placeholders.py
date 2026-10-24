"""Event placeholders shared by every email editor."""

import datetime

import pytest
from django.utils.formats import date_format
from django.utils.translation import override
from django_scopes import scopes_disabled

from eventyay.base.email import get_available_placeholders, get_email_context
from eventyay.base.models import Event, Organizer


SHARED = (
    'event_name',
    'event_url',
    'event_dates',
    'event_start_date',
    'event_end_date',
    'event_location',
    'organizer_name',
    'event_contact_email',
)


@pytest.fixture
def event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='FOSSASIA', slug='fossasia-shared')
        event = Event.objects.create(
            organizer=organizer,
            name='Summit',
            slug='summit',
            location='Singapore',
            date_from=datetime.datetime(2026, 11, 5, 10, tzinfo=datetime.UTC),
            date_to=datetime.datetime(2026, 11, 7, 18, tzinfo=datetime.UTC),
        )
        event.settings.timezone = 'UTC'
        event.settings.contact_mail = 'team@summit.example'
        yield event


def _context(event):
    with override('en'):
        return {key: str(value) for key, value in get_email_context(event=event).items()}


@pytest.mark.django_db
def test_shared_event_placeholders_are_offered_on_every_event(event):
    available = get_available_placeholders(event, ['event'])

    for identifier in SHARED:
        assert identifier in available


@pytest.mark.django_db
def test_shared_event_placeholders_render_event_details(event):
    context = _context(event)

    assert context['event_name'] == 'Summit'
    assert context['event_url'].endswith('/fossasia-shared/summit/')
    with override('en'):
        assert context['event_start_date'] == date_format(event.date_from, 'DATE_FORMAT')
        assert context['event_end_date'] == date_format(event.date_to, 'DATE_FORMAT')
    assert context['event_location'] == 'Singapore'
    assert context['organizer_name'] == 'FOSSASIA'
    assert context['event_contact_email'] == 'team@summit.example'


@pytest.mark.django_db
def test_event_dates_matches_the_event_page(event):
    with override('en'):
        expected = event.get_date_range_display()

    assert _context(event)['event_dates'] == expected


@pytest.mark.django_db
def test_old_organizer_placeholder_still_renders_but_is_hidden(event):
    assert _context(event)['organizer'] == 'FOSSASIA'
    assert get_available_placeholders(event, ['event'])['organizer'].is_visible is False


@pytest.mark.django_db
def test_missing_location_and_contact_email_render_empty(event):
    event.location = ''
    event.save()
    event.settings.delete('contact_mail')

    context = _context(event)

    assert context['event_location'] == ''
    assert context['event_contact_email'] == ''
