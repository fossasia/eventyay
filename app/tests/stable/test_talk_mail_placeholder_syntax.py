import pytest
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.models import MailTemplate, Team
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
