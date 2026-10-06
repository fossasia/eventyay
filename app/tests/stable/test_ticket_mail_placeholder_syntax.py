import json
from datetime import timedelta

import pytest
from django.utils import timezone
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Order, Team
from eventyay.control.forms.orders import OrderMailForm
from eventyay.plugins.sendmail.forms import TeamMailForm

STRAY_BRACE_ERROR = 'Invalid placeholder syntax'


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('subject', 'message', 'field'),
    [
        ('Volunteer briefing for {event_name', 'Hello', 'subject'),
        ('Volunteer briefing', 'See you there :}', 'message'),
    ],
)
def test_team_mail_form_rejects_stray_brace(event, subject, message, field):
    with scope(event=event):
        form = TeamMailForm(event=event, data={'subject_0': subject, 'message_0': message})
        assert not form.is_valid()
    assert STRAY_BRACE_ERROR in str(form.errors[field])


@pytest.mark.django_db
def test_team_mail_form_accepts_known_placeholder(event):
    with scope(event=event):
        form = TeamMailForm(event=event, data={'subject_0': 'Briefing for {event_name}', 'message_0': 'Hi {name}'})
        form.is_valid()
    assert 'subject' not in form.errors
    assert 'message' not in form.errors


@pytest.mark.django_db
def test_order_mail_form_rejects_stray_brace_in_subject(event, order):
    with scope(event=event):
        form = OrderMailForm(
            order=order,
            data={'subject': 'Your order for {event', 'message': 'Hello', 'sendto': order.email},
        )
        assert not form.is_valid()
    assert STRAY_BRACE_ERROR in str(form.errors['subject'])


@pytest.mark.django_db
def test_order_send_mail_with_stray_brace_shows_form_error(mail_client, event, order):
    response = mail_client.post(
        event_url(event, f'orders/{order.code}/sendmail'),
        {'subject': 'Your order for {event', 'message': 'Hello', 'sendto': order.email},
        secure=True,
    )
    assert response.status_code == 200
    assert STRAY_BRACE_ERROR in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('text', ['See you there :}', 'See you there {'])
def test_order_mail_preview_returns_validation_error(mail_client, event, order, text):
    response = mail_client.post(
        event_url(event, f'orders/{order.code}/sendmail/preview'),
        {'content': text},
        secure=True,
    )
    assert response.status_code == 400
    assert 'stray { or }' in response.json()['error']


@pytest.mark.django_db
def test_order_mail_preview_renders_placeholders(mail_client, event, order):
    response = mail_client.post(
        event_url(event, f'orders/{order.code}/sendmail/preview'),
        {'content': 'Order {code} {{literal}}'},
        secure=True,
    )
    assert response.status_code == 200
    html = response.json()['html']
    assert order.code in html
    assert '{literal}' in html


@pytest.mark.django_db
@pytest.mark.parametrize('payload_format', ['form', 'json'])
def test_editor_email_preview_returns_validation_error(mail_client, event, payload_format):
    url = event_url(event, 'editor/email-preview')
    if payload_format == 'json':
        response = mail_client.post(
            url,
            data=json.dumps({'html': '<p>See you there :}</p>', 'locale': 'en'}),
            content_type='application/json',
            secure=True,
        )
    else:
        response = mail_client.post(url, {'body_en': '<p>See you there :}</p>'}, secure=True)
    assert response.status_code == 400
    assert 'stray { or }' in response.json()['error']


@pytest.mark.django_db
def test_editor_email_preview_renders_placeholders(mail_client, event):
    response = mail_client.post(
        event_url(event, 'editor/email-preview'),
        {'body_en': '<p>{{literal}} {event_name}</p>'},
        secure=True,
    )
    assert response.status_code == 200
    html = response.json()['previews']['en']
    assert '{literal}' in html
    assert '<span class="placeholder"' in html


@pytest.mark.django_db
def test_team_mail_form_accepts_escaped_braces(event):
    with scope(event=event):
        form = TeamMailForm(
            event=event,
            data={'subject_0': 'Briefing {{internal}} for {event_name}', 'message_0': 'Use {{name}} literally, {name}'},
        )
        form.is_valid()
    assert 'subject' not in form.errors
    assert 'message' not in form.errors


@pytest.mark.django_db
def test_order_mail_form_accepts_escaped_braces_in_subject(event, order):
    with scope(event=event):
        form = OrderMailForm(
            order=order,
            data={'subject': 'Order {code} {{internal}}', 'message': 'Hello', 'sendto': order.email},
        )
        form.is_valid()
    assert 'subject' not in form.errors


@pytest.mark.django_db
def test_team_mail_ajax_preview_returns_escaped_field_errors(mail_client, event):
    response = mail_client.post(
        event_url(event, 'mails/compose/teams/'),
        {'action': 'preview', 'subject_0': 'Briefing for {<b>x</b>}', 'message_0': 'See you there :}'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        secure=True,
    )
    assert response.status_code == 400
    errors = response.json()['errors']
    assert STRAY_BRACE_ERROR in errors['Message'][0]
    assert '&lt;b&gt;x&lt;/b&gt;' in errors['Subject'][0]
    assert '<b>' not in errors['Subject'][0]
