import json

import pytest
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.base.email import get_available_placeholders
from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.services.mail import mail
from eventyay.plugins.sendmail.forms import (
    SYSTEM_MAIL_TEMPLATES,
    MailContentSettingsForm,
    TicketMailBodyFormField,
)


@pytest.fixture
def template_event(db):
    """Provide a multilingual ticket event for transactional email templates."""
    organizer = Organizer.objects.create(name='Template tests', slug='template-tests')
    event = Event.objects.create(
        organizer=organizer, name='Template event', slug='templates', date_from=now(),
        plugins='eventyay.plugins.sendmail',
    )
    event.settings.locales = ['en', 'de']
    return event


@pytest.fixture
def template_client(client, template_event, settings):
    """Authenticate an organiser allowed to edit the event's email settings."""
    user = User.objects.create_user('editor@example.test', 'test')
    team = Team.objects.create(organizer=template_event.organizer, can_change_event_settings=True)
    team.members.add(user)
    team.limit_events.add(template_event)
    client.force_login(user)
    settings.DEBUG = True
    return client


@pytest.mark.parametrize('template_key', tuple(SYSTEM_MAIL_TEMPLATES))
def test_all_template_fields_use_scoped_email_editor(template_event, template_key):
    """Expose the shared editor and only valid variables for every template body."""
    if template_key == 'meetup_registration':
        template_event.settings.event_type = 'meetup'
    with scope(event=template_event, organizer=template_event.organizer):
        form = MailContentSettingsForm(obj=template_event, template_key=template_key)
        for name, contexts in form.base_context.items():
            if name not in form.fields:
                continue
            assert isinstance(form.fields[name], TicketMailBodyFormField)
            page = BeautifulSoup(str(form[name]), 'html.parser')
            assert len(page.select('[data-email-editor]')) == 2
            expected = sorted(get_available_placeholders(template_event, contexts))
            for textarea in page.select('textarea'):
                assert textarea['data-tiptap-profile'] == 'email'
                assert json.loads(textarea['data-tiptap-placeholders']) == expected
                assert '{event}' in textarea.get_text()


def test_legacy_template_content_and_locales_are_preserved(template_event):
    """Opening legacy text preserves line breaks, Markdown and locale placeholders."""
    original = {'en': 'Hello {event}\nSecond line\n\n**Important**', 'de': 'Hallo {event}\nZweite Zeile'}
    template_event.settings.mail_text_order_placed = LazyI18nString(original)
    form = MailContentSettingsForm(obj=template_event, template_key='order_placed')
    page = BeautifulSoup(str(form['mail_text_order_placed']), 'html.parser')
    values = {field['lang']: field.get_text() for field in page.select('textarea')}
    assert 'Hello {event}<br' in values['en']
    assert '<strong>Important</strong>' in values['en']
    assert 'Hallo {event}<br' in values['de']
    assert template_event.settings.mail_text_order_placed.data == original


def test_template_placeholder_menu_matches_validation(template_event):
    """Contact and attendee bodies retain different allowed placeholder sets."""
    form = MailContentSettingsForm(obj=template_event, template_key='order_placed')
    contact = form.fields['mail_text_order_placed']
    attendee = form.fields['mail_text_order_placed_attendee']
    assert 'payment_info' in json.loads(contact.widget.attrs['data-tiptap-placeholders'])
    assert 'payment_info' not in json.loads(attendee.widget.attrs['data-tiptap-placeholders'])
    assert 'attendee_name' in json.loads(attendee.widget.attrs['data-tiptap-placeholders'])
    with pytest.raises(ValidationError):
        attendee.clean(['<p>{payment_info}</p>'])


def test_template_save_preview_and_delivery(template_event, template_client, mailoutbox):
    """Save both bodies, preview HTML and verify formatted delivery with filled variables."""
    contact = '<h2>Hello {event}</h2><p><strong>Bold</strong> <em>Italic</em> <u>Underlined</u><br>Next line</p>'
    contact += '<ul><li>First</li></ul><p><a href="https://example.test/help">Help</a></p>'
    contact += '<p><a href="{url}">Order details</a></p>'
    attendee = '<p>Welcome {attendee_name}</p><p><strong>Your ticket</strong></p>'
    kwargs = {'organizer': template_event.organizer.slug, 'event': template_event.slug}
    url = reverse('control:event.mail.templates.system', kwargs={**kwargs, 'template_key': 'order_placed'})
    response = template_client.post(url, {
        'mail_text_order_placed_0': contact, 'mail_text_order_placed_1': '<p>Hallo {event}</p>',
        'mail_send_order_placed_attendee': 'on',
        'mail_text_order_placed_attendee_0': attendee,
        'mail_text_order_placed_attendee_1': '<p>Hallo {attendee_name}</p>',
    })
    assert response.status_code == 302, (response.content.decode()[:2000], dict(response.items()))
    assert response.url == reverse('control:event.mail.templates', kwargs=kwargs)
    template_event = Event.objects.get(pk=template_event.pk)
    assert template_event.settings.mail_text_order_placed.data['en'] == contact
    assert template_event.settings.mail_text_order_placed_attendee.data['en'] == attendee
    preview = template_client.post(reverse('control:event.settings.mail.preview', kwargs=kwargs), {
        'product': 'mail_text_order_placed', 'mail_text_order_placed_0': contact,
    })
    assert preview.status_code == 200
    html = preview.json()['msgs']['en']
    for markup in ('<h2>', '<strong>Bold</strong>', '<em>Italic</em>', '<u>Underlined</u>', '<br>', '<ul>', 'href="https://example.test/help"'):
        assert markup in html
    assert '{event}' not in html
    link = BeautifulSoup(html, 'html.parser').find('a', string='Order details')
    assert link['href'].startswith('http')
    assert '<' not in link['href']
    with scope(event=template_event, organizer=template_event.organizer):
        mail(
            'recipient@example.test', 'Template test', template_event.settings.mail_text_order_placed,
            {'event': 'Template event', 'url': 'https://example.test/order/'},
            event=template_event, locale='en', sync_send=True,
        )
        mail(
            'attendee@example.test', 'Attendee test', template_event.settings.mail_text_order_placed_attendee,
            {'attendee_name': 'Demo attendee'}, event=template_event, locale='en', sync_send=True,
        )
    assert len(mailoutbox) == 2
    sent_html = next(
        part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
        for part in mailoutbox[0].alternatives[0][0].walk()
        if part.get_content_type() == 'text/html'
    )
    sent_page = BeautifulSoup(sent_html, 'html.parser')
    assert sent_page.find('h2', string='Hello Template event')
    assert sent_page.find('u', string='Underlined')
    assert sent_page.find('strong', string='Bold')
    assert sent_page.find('a', href='https://example.test/help')
    assert sent_page.find('a', href='https://example.test/order/')
    assert '{event}' not in sent_html
    attendee_html = next(
        part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
        for part in mailoutbox[1].alternatives[0][0].walk()
        if part.get_content_type() == 'text/html'
    )
    assert 'Welcome Demo attendee' in attendee_html


def test_template_editor_sanitizes_html(template_event):
    """Keep normal email markup while removing executable HTML from submitted bodies."""
    form = MailContentSettingsForm(obj=template_event, template_key='order_placed')
    field = form.fields['mail_text_order_placed']
    value = field.clean(['<p><strong>Safe</strong><script>alert(1)</script></p>'])
    assert value.data['en'] == '<p><strong>Safe</strong></p>'
