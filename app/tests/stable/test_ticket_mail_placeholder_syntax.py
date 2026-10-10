import json
from datetime import timedelta

import pytest
from django.core import mail as djmail
from django.utils import timezone
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Order, Team
from eventyay.control.forms.orders import OrderMailForm
from eventyay.helpers.placeholders import escape_stray_braces, find_placeholders
from eventyay.plugins.sendmail.forms import TeamMailForm

# The subject and message from the #6251 review recording.
REVIEW_SUBJECT = 'TEST "{"    Chai ki Tapri "}"'
REVIEW_MESSAGE = 'TEST {} {event_name}'


@pytest.fixture
def order(event):
    with scope(event=event):
        return Order.objects.create(
            event=event,
            code='BRACE',
            email='buyer@example.org',
            status=Order.STATUS_PAID,
            datetime=timezone.now(),
            expires=timezone.now() + timedelta(days=1),
            total=10,
            locale='en',
        )


@pytest.fixture
def mail_client(client, user, event, settings):
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scopes_disabled():
        team = Team.objects.create(
            organizer=event.organizer,
            name='Mail senders',
            can_change_event_settings=True,
            can_change_orders=True,
            can_view_orders=True,
        )
        team.limit_events.add(event)
        team.members.add(user)
    client.force_login(user)
    return client


def event_url(event, path):
    return f'/control/event/{event.organizer.slug}/{event.slug}/{path}'


@pytest.mark.parametrize(
    ('template', 'rendered'),
    [
        (REVIEW_SUBJECT, REVIEW_SUBJECT),
        ('TEST {} {event_name}', 'TEST {} Test Event'),
        ('Volunteer briefing for {event_name', 'Volunteer briefing for {event_name'),
        ('See you there :}', 'See you there :}'),
        ('{{literal}} {event_name}', '{literal} Test Event'),
        ('{event.name} {0} {a:>5} }{', '{event.name} {0} {a:>5} }{'),
    ],
)
def test_escape_stray_braces_keeps_only_placeholders(template, rendered):
    assert escape_stray_braces(template).format_map({'event_name': 'Test Event'}) == rendered


def test_find_placeholders_ignores_literal_braces():
    assert find_placeholders('{" x "} {} {{y}} {event_name} {join\\_online\\_event}') == [
        '{event_name}',
        '{join_online_event}',
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('subject', 'message'),
    [
        (REVIEW_SUBJECT, REVIEW_MESSAGE),
        ('Volunteer briefing for {event_name', 'See you there :}'),
        ('Briefing {{internal}} for {event_name}', 'Use {{name}} literally, {name}'),
    ],
)
def test_team_mail_form_accepts_braces_as_text(event, subject, message):
    with scope(event=event):
        form = TeamMailForm(event=event, data={'subject_0': subject, 'message_0': message})
        form.is_valid()
    assert 'subject' not in form.errors
    assert 'message' not in form.errors


@pytest.mark.django_db
def test_team_mail_form_still_rejects_misspelled_placeholder(event):
    with scope(event=event):
        form = TeamMailForm(event=event, data={'subject_0': 'Briefing for {evnt_name}', 'message_0': 'Hi'})
        assert not form.is_valid()
    assert 'Invalid placeholder(s): {evnt_name}' in str(form.errors['subject'])


@pytest.mark.django_db
def test_order_mail_form_accepts_braces_as_text(event, order):
    with scope(event=event):
        form = OrderMailForm(
            order=order,
            data={'subject': REVIEW_SUBJECT, 'message': 'See you there :}', 'sendto': order.email},
        )
        form.is_valid()
    assert 'subject' not in form.errors
    assert 'message' not in form.errors


@pytest.mark.django_db
def test_order_send_mail_keeps_braces_in_sent_email(mail_client, event, order):
    djmail.outbox = []
    response = mail_client.post(
        event_url(event, f'orders/{order.code}/sendmail'),
        {'subject': REVIEW_SUBJECT, 'message': 'Order {code}. See you there :}', 'sendto': order.email},
        secure=True,
    )
    assert response.status_code == 302
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].subject == REVIEW_SUBJECT
    assert f'Order {order.code}. See you there :}}' in djmail.outbox[0].body


@pytest.mark.django_db
def test_order_mail_preview_renders_braces_as_text(mail_client, event, order):
    response = mail_client.post(
        event_url(event, f'orders/{order.code}/sendmail/preview'),
        {'content': 'Order {code} {{literal}} {} See you there :}'},
        secure=True,
    )
    assert response.status_code == 200
    html = response.json()['html']
    assert f'Order {order.code} {{literal}} {{}} See you there :}}' in html


@pytest.mark.django_db
@pytest.mark.parametrize('payload_format', ['form', 'json'])
def test_editor_email_preview_renders_braces_as_text(mail_client, event, payload_format):
    url = event_url(event, 'editor/email-preview')
    body = '<p>TEST {} {event_name} {all_submissions_url} See you there :}</p>'
    if payload_format == 'json':
        response = mail_client.post(
            url, data=json.dumps({'html': body, 'locale': 'en'}), content_type='application/json', secure=True
        )
        html = response.json()['html']
    else:
        response = mail_client.post(url, {'body_en': body}, secure=True)
        html = response.json()['previews']['en']
    assert response.status_code == 200
    assert 'TEST {}' in html
    assert 'See you there :}' in html
    assert '<span class="placeholder"' in html
    assert '/me/submissions/' in html


@pytest.mark.django_db
def test_team_mail_ajax_preview_renders_review_input(mail_client, event):
    response = mail_client.post(
        event_url(event, 'mails/compose/teams/'),
        {'action': 'preview', 'subject_0': REVIEW_SUBJECT, 'message_0': REVIEW_MESSAGE},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        secure=True,
    )
    assert response.status_code == 200
    html = response.json()['html']
    assert 'Chai ki Tapri' in html
    assert 'TEST {}' in html


@pytest.mark.django_db
def test_team_mail_ajax_preview_returns_field_errors(mail_client, event):
    response = mail_client.post(
        event_url(event, 'mails/compose/teams/'),
        {'action': 'preview', 'subject_0': 'Briefing for {evnt_name}', 'message_0': 'Hi'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        secure=True,
    )
    assert response.status_code == 400
    assert 'Invalid placeholder(s): {evnt_name}' in response.json()['errors']['Subject'][0]
