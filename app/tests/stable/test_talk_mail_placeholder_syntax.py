from types import SimpleNamespace
from unittest import mock

import pytest
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.api.serializers.mail import MailTemplateSerializer
from eventyay.base.models import MailTemplate, Team
from eventyay.helpers.placeholders import escape_stray_braces, find_malformed_placeholders, find_placeholder_names
from eventyay.mail.context import get_malformed_placeholders, get_used_placeholders

# The subject from the #6251 review recording.
REVIEW_SUBJECT = 'TEST "{"    Chai ki Tapri "}"'


@pytest.fixture
def orga_client(client, user, event, settings):
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scopes_disabled():
        team = Team.objects.create(
            organizer=event.organizer,
            name='Mail editors',
            can_change_event_settings=True,
            can_change_submissions=True,
        )
        team.limit_events.add(event)
        team.members.add(user)
    client.force_login(user)
    return client


def test_used_placeholders_treat_stray_braces_as_text():
    assert get_used_placeholders('TEST {} {event_name} {{name}} {join\\_online\\_event} See you :} {') == {
        'event_name',
        'join_online_event',
    }


def test_malformed_placeholders_checks_every_language():
    text = LazyI18nString({'en': 'Hi { name }, {draft', 'de': 'Hallo {name'})
    assert get_malformed_placeholders(text, {'name': None}) == ['{ name }', '{name']


def test_malformed_placeholders_are_reported_once():
    text = LazyI18nString({'en': 'Hi { name }, see you { name }', 'de': 'Hallo { name }, {name'})
    assert get_malformed_placeholders(text, {'name': None}) == ['{ name }', '{name']


def test_excessive_format_width_is_never_evaluated():
    template = '{event_name:>99999} {other:>1000000000}'
    with mock.patch('eventyay.helpers.placeholders.format', create=True, side_effect=AssertionError) as evaluate:
        assert find_placeholder_names(template) == []
        assert find_malformed_placeholders(template, {'event_name'}) == ['{event_name:>99999}']
        assert escape_stray_braces(template) == '{{event_name:>99999}} {{other:>1000000000}}'
    evaluate.assert_not_called()


def test_escape_stray_braces_rewrites_markdown_escaped_names():
    assert escape_stray_braces('{join\\_online\\_event:>5} {{a\\_b}}') == '{join_online_event:>5} {{a\\_b}}'


@pytest.mark.django_db
def test_markdown_escaped_placeholder_is_saved_and_expanded(orga_client, event):
    with scope(event=event):
        template = MailTemplate.objects.create(event=event, subject='Old subject', text='Hello')
    response = orga_client.post(
        template.urls.edit,
        {'subject_0': 'About {event\\_name}', 'text_0': 'Welcome to {event\\_name}'},
        follow=True,
        secure=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        template.refresh_from_db()
        mail = template.to_mail(user='speaker@example.org', event=event, commit=False)
    assert 'About Test Event' in mail.subject
    assert mail.text == 'Welcome to Test Event'


@pytest.mark.django_db
def test_mail_template_renders_braces_as_text(event):
    with scope(event=event):
        template = MailTemplate.objects.create(
            event=event,
            subject=REVIEW_SUBJECT + ' {event_name}',
            text='TEST {} {event_name} {{literal}} See you there :}',
        )
        mail = template.to_mail(user='speaker@example.org', event=event, commit=False)
    assert REVIEW_SUBJECT + ' Test Event' in mail.subject
    assert mail.text == 'TEST {} Test Event {literal} See you there :}'


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('subject', 'saved'),
    [
        (REVIEW_SUBJECT, True),
        ('Volunteer briefing {draft', True),
        ('Volunteer briefing for {event_name', False),
        ('Volunteer briefing for { event_name }', False),
        ('Volunteer briefing for {event_name!x}', False),
    ],
)
def test_mail_template_form_accepts_braces_but_not_mistyped_placeholders(orga_client, event, subject, saved):
    with scope(event=event):
        template = MailTemplate.objects.create(event=event, subject='Old subject', text='Hello')
    response = orga_client.post(
        template.urls.edit,
        {'subject_0': subject, 'text_0': 'TEST {} {event_name} See you there :}'},
        follow=True,
        secure=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        template.refresh_from_db()
    if saved:
        assert str(template.subject) == subject
        assert str(template.text) == 'TEST {} {event_name} See you there :}'
    else:
        assert str(template.subject) == 'Old subject'
        assert 'Invalid placeholder syntax' in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('value', 'error'),
    [
        (REVIEW_SUBJECT, None),
        ('TEST {} {event_name} See you there :}', None),
        ('Volunteer briefing {draft', None),
        ('Volunteer briefing for {event_name', 'Invalid placeholder syntax'),
        ('Volunteer briefing for { event_name }', 'Invalid placeholder syntax'),
        ('Volunteer briefing for {invalidplaceholder}', 'Unknown placeholder'),
    ],
)
def test_mail_template_api_accepts_braces_but_not_mistyped_placeholders(event, value, error):
    with scope(event=event):
        template = MailTemplate.objects.create(event=event, subject='Old subject', text='Hello')
        serializer = MailTemplateSerializer(
            template,
            data={'subject': value, 'text': value},
            partial=True,
            context={'request': SimpleNamespace(event=event)},
        )
        is_valid = serializer.is_valid()
    if error is None:
        assert is_valid, serializer.errors
    else:
        assert not is_valid
        assert set(serializer.errors) == {'subject', 'text'}
        assert error in str(serializer.errors['subject'][0])
