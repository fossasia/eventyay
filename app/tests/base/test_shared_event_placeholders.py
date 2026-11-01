"""Event placeholders shared by every email editor."""

import datetime
import importlib
from types import SimpleNamespace

import pytest
from django.utils.formats import date_format
from django.utils.translation import override
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.email import get_available_placeholders, get_email_context
from eventyay.base.models import Event, Organizer, User, Voucher
from eventyay.base.templatetags.rich_text import build_email_preview_context
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue


rename_placeholder = importlib.import_module(
    'eventyay.base.migrations.0089_rename_organizer_placeholder'
).rename_placeholder


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
def test_organizer_is_only_offered_as_organizer_name(event):
    assert 'organizer' not in get_available_placeholders(event, ['event'])


@pytest.mark.django_db
def test_missing_location_and_contact_email_render_empty(event):
    event.location = ''
    event.save()
    event.settings.delete('contact_mail')

    context = _context(event)

    assert context['event_location'] == ''
    assert context['event_contact_email'] == ''


@pytest.mark.django_db
def test_sendmail_preview_shows_the_tickets_event_url(event):
    preview = build_email_preview_context(event, ['event'], shared_event_values=True)

    assert '/fossasia-shared/summit/' in preview['event_url']


@pytest.mark.django_db
def test_talk_preview_keeps_the_talk_event_url(event):
    preview = build_email_preview_context(event, ['event'])

    assert 'https://eventyay.com/summit/' in preview['event_url']


@pytest.mark.django_db
def test_team_mail_uses_the_shared_event_url(event):
    User.objects.create_user(email='member@summit.example', password='pw')
    with scopes_disabled():
        queue = EmailQueue.objects.create(event=event, composing_for=ComposingFor.TEAMS)
        context = queue._build_email_context(None, None, None, SimpleNamespace(email='member@summit.example'))

    assert context['event_url'].endswith('/fossasia-shared/summit/')


@pytest.mark.django_db
def test_empty_location_and_contact_email_preview_blank(event):
    event.location = ''
    event.save()
    event.settings.delete('contact_mail')

    available = get_available_placeholders(event, ['event'])

    assert str(available['event_location'].render_sample(event)) == ''
    assert available['event_contact_email'].render_sample(event) == ''


@pytest.mark.django_db
def test_location_is_translated_into_the_email_language(event):
    event.location = LazyI18nString({'en': 'Singapore', 'de': 'Singapur'})
    event.save()
    with scopes_disabled():
        location = get_email_context(event=event)['event_location']

    with override('de'):
        assert str(location) == 'Singapur'


@pytest.mark.django_db
def test_voucher_placeholders_render_the_code_and_its_redeem_link(event):
    with scopes_disabled():
        voucher = Voucher.objects.create(event=event, code='A B&C')
        context = get_email_context(event=event, voucher=voucher)

    assert context['voucher_code'] == 'A B&C'
    assert '/fossasia-shared/summit/redeem' in context['voucher_redeem_url']
    assert context['voucher_redeem_url'].endswith('?voucher=A%20B%26C')


def test_rename_placeholder_renames_braces_and_editor_chips():
    html = '<p>{organizer} <span data-variable="organizer">{organizer}</span> {organizer_name}</p>'

    assert rename_placeholder(html, 'organizer', 'organizer_name') == (
        '<p>{organizer_name} <span data-variable="organizer_name">{organizer_name}</span> {organizer_name}</p>'
    )


def test_rename_placeholder_handles_json_escaped_chips():
    stored = '{"en": "<span data-variable=\\"organizer\\">{organizer}</span>"}'

    assert rename_placeholder(stored, 'organizer', 'organizer_name') == (
        '{"en": "<span data-variable=\\"organizer_name\\">{organizer_name}</span>"}'
    )
