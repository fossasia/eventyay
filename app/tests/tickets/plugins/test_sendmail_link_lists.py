import datetime
import json

import pytest
from django.core import mail as djmail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, Team, User
from eventyay.plugins.sendmail.forms import MailForm
from eventyay.plugins.sendmail.link_lists import add_rows, create_link_list, parse_link_list
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueToUser, MailLinkList


def _csv(text, name='partner-links.csv'):
    return SimpleUploadedFile(name, text.encode(), content_type='text/csv')


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(
        organizer=organizer, name='Dummy', slug='dummy', date_from=now(), plugins='tests.tickets.testdummy'
    )


@pytest.fixture
def order(event):
    product = Product.objects.create(name='Ticket', event=event, default_price=13)
    order = Order.objects.create(
        event=event,
        status=Order.STATUS_PAID,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='LINKS',
        email='buyer@example.com',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=order, product=product, price=13)
    return order


@pytest.fixture
def link_list(event):
    parsed = parse_link_list(_csv('Link,Code\nhttps://p.test/a,A1\nhttps://p.test/b,B2\n'))
    return create_link_list(event, 'Partner discounts', parsed)[0]


@pytest.fixture
def logged_in_client(client, event):
    user = User.objects.create_superuser('organizer@example.com', 'pw')
    team = Team.objects.create(organizer=event.organizer, can_view_orders=True, can_change_orders=True)
    team.members.add(user)
    team.limit_events.add(event)
    client.force_login(user)
    return client


def _rows_url(event, link_list):
    return f'/control/event/{event.organizer.slug}/{event.slug}/sendmail/link-lists/{link_list.pk}/rows/'


def test_parse_turns_the_header_into_placeholder_columns():
    parsed = parse_link_list(_csv('Meeting Link;Room #\nhttps://m.test/1;A\n'))

    assert parsed.columns == ['meeting_link', 'room']
    assert parsed.rows == [{'meeting_link': 'https://m.test/1', 'room': 'A'}]


def test_parse_rejects_a_file_without_rows():
    with pytest.raises(ValidationError):
        parse_link_list(_csv('link\n'))


@pytest.mark.django_db
def test_rows_skip_empty_and_repeated_values(event, link_list):
    with scopes_disabled():
        added, skipped = add_rows(
            link_list,
            [{'link': 'https://p.test/c', 'code': 'C3'}, {'link': 'https://p.test/a', 'code': 'A1'}, {'link': ''}],
        )

        assert (added, skipped) == (1, 2)
        assert link_list.counts() == {'total': 3, 'used': 0, 'left': 3}


@pytest.mark.django_db
def test_each_address_keeps_its_own_row(event, link_list):
    with scopes_disabled():
        first = link_list.assign('Ali@Example.com')
        again = link_list.assign(' ali@example.com ')
        second = link_list.assign('sara@example.com')
        none_left = link_list.assign('john@example.com')

        assert first.pk == again.pk
        assert first.values == {'link': 'https://p.test/a', 'code': 'A1'}
        assert second.values == {'link': 'https://p.test/b', 'code': 'B2'}
        assert none_left is None
        assert link_list.shortfall(['ali@example.com', 'john@example.com', 'mia@example.com']) == 2


def _queue(event, order, link_list, emails):
    queued = EmailQueue.objects.create(
        event=event,
        composing_for=ComposingFor.ATTENDEES,
        subject={'en': 'Your discount'},
        message={'en': 'Use {list_link} with code {list_code}'},
        link_list=link_list,
    )
    for email in emails:
        EmailQueueToUser.objects.create(mail=queued, email=email, orders=[order.pk])
    return queued


@pytest.mark.django_db
def test_sending_gives_each_recipient_their_row(event, order, link_list):
    djmail.outbox = []
    with scopes_disabled():
        _queue(event, order, link_list, ('ali@example.com', 'sara@example.com')).send(async_send=False)

    rows = {('https://p.test/a', 'A1'), ('https://p.test/b', 'B2')}
    by_recipient = {message.to[0]: message.body for message in djmail.outbox}
    assert len(djmail.outbox) == 2
    given = {
        email: [(link, code) for link, code in rows if link in body and code in body]
        for email, body in by_recipient.items()
    }
    assert all(len(matches) == 1 for matches in given.values())
    assert {matches[0] for matches in given.values()} == rows


@pytest.mark.django_db
def test_nothing_is_sent_when_the_list_is_too_short(event, order, link_list):
    djmail.outbox = []
    with scopes_disabled():
        queued = _queue(event, order, link_list, ('ali@example.com', 'sara@example.com', 'john@example.com'))

        assert queued.send(async_send=False) is False

        assert link_list.counts()['used'] == 0
        errors = set(queued.recipients.values_list('error', flat=True))
    assert djmail.outbox == []
    assert len(errors) == 1
    assert 'too few unused rows' in errors.pop()


@pytest.mark.django_db
def test_a_scheduled_email_short_of_rows_leaves_the_schedule(event, order, link_list):
    with scopes_disabled():
        queued = _queue(event, order, link_list, ('ali@example.com', 'sara@example.com', 'john@example.com'))
        queued.scheduled_at = now() - datetime.timedelta(minutes=1)
        queued.save(update_fields=['scheduled_at'])

        assert queued.send(async_send=False) is False
        queued.refresh_from_db()

    assert queued.scheduled_at is None
    assert queued.sent_at is None


@pytest.mark.django_db
def test_deleting_a_list_keeps_the_queued_email(event, order, link_list):
    with scopes_disabled():
        queued = _queue(event, order, link_list, ('ali@example.com',))
        link_list.delete()
        queued.refresh_from_db()

    assert queued.link_list_id is None


def test_repeated_and_long_headers_keep_their_own_values():
    parsed = parse_link_list(_csv(f'Link,Link,{"x" * 150}\na,b,c\n'))

    assert parsed.columns[:2] == ['link', 'link_2']
    assert len(parsed.columns[2]) <= 90
    assert list(parsed.rows[0].values()) == ['a', 'b', 'c']


@pytest.mark.django_db
def test_compose_form_needs_a_list_for_list_placeholders(event, link_list):
    with scopes_disabled():
        without_list = MailForm(event=event, data={'subject_0': 'Hi', 'text_0': 'Your link: {list_link}'})
        both = MailForm(
            event=event,
            data={'subject_0': 'Hi', 'text_0': 'Your seat: {list_seat}', 'link_list': link_list.pk},
            files={'link_list_file': _csv('Seat\n12A\n')},
        )
        with_list = MailForm(
            event=event, data={'subject_0': 'Hi', 'text_0': 'Your link: {list_link}', 'link_list': link_list.pk}
        )

        without_list.is_valid()
        both.is_valid()
        with_list.is_valid()

    assert 'link_list' in without_list.errors
    assert 'link_list_file' in both.errors
    assert 'text' not in both.errors
    assert 'link_list' not in with_list.errors
    assert 'text' not in with_list.errors


@pytest.mark.django_db
def test_dialog_adds_rows_from_a_csv(logged_in_client, event, link_list):
    with scopes_disabled():
        link_list.assign('ali@example.com')

    response = logged_in_client.post(
        _rows_url(event, link_list), {'file': _csv('link,code\nhttps://p.test/c,C3\nhttps://p.test/a,A1\n')}
    )

    assert response.json() == {'total': 3, 'used': 1, 'left': 2, 'added': 1, 'skipped': 1}


@pytest.mark.django_db
def test_dialog_rejects_a_csv_missing_any_list_column(logged_in_client, event, link_list):
    response = logged_in_client.post(_rows_url(event, link_list), {'file': _csv('link\nhttps://p.test/c\n')})

    assert response.status_code == 400
    assert 'code' in response.json()['error']


@pytest.mark.django_db
def test_lists_belong_to_their_event(logged_in_client, event):
    other_event = Event.objects.create(
        organizer=event.organizer, name='Other', slug='other', date_from=now(), plugins='tests.tickets.testdummy'
    )
    with scopes_disabled():
        foreign = MailLinkList.objects.create(event=other_event, name='Other', columns=['link'])

    response = logged_in_client.post(_rows_url(event, foreign), {'file': _csv('link\nhttps://p.test/x\n')})

    assert response.status_code == 404


def _preview_html(client, event, payload):
    url = f'/control/event/{event.organizer.slug}/{event.slug}/editor/email-preview'
    return client.post(url, data=json.dumps(payload), content_type='application/json').json()['html']


@pytest.mark.django_db
def test_editor_preview_fills_in_a_row_of_the_chosen_list(logged_in_client, event, link_list):
    saved = _preview_html(logged_in_client, event, {'html': '<p>{list_link}</p>', 'link_list': link_list.pk})
    unsaved = _preview_html(
        logged_in_client, event, {'html': '<p>{list_seat}</p>', 'link_list_sample': {'list_seat': '12A'}}
    )

    assert 'https://p.test/a' in saved
    assert '12A' in unsaved


@pytest.mark.django_db
def test_editor_preview_escapes_list_values(logged_in_client, event):
    html = _preview_html(
        logged_in_client,
        event,
        {'html': '<p>{list_link}</p>', 'link_list_sample': {'list_link': '<img src=x onerror=alert(1)>'}},
    )

    assert '<img' not in html
    assert '&lt;img' in html


@pytest.mark.django_db
def test_editor_preview_drops_script_links_from_list_values(logged_in_client, event):
    html = _preview_html(
        logged_in_client,
        event,
        {'html': '<p><a href="{list_link}">Open</a></p>', 'link_list_sample': {'list_link': 'javascript:alert(1)'}},
    )

    assert 'javascript:' not in html
    assert 'Open' in html


@pytest.mark.django_db
def test_rows_are_reserved_for_every_recipient_or_none(event, link_list):
    with scopes_disabled():
        too_many = link_list.reserve(['ali@example.com', 'sara@example.com', 'john@example.com'])
        used_after_refusal = link_list.counts()['used']
        enough = link_list.reserve(['ali@example.com', 'sara@example.com'])

        assert not too_many
        assert used_after_refusal == 0
        assert enough
        assert link_list.counts() == {'total': 2, 'used': 2, 'left': 0}


@pytest.mark.django_db
def test_test_emails_show_made_up_list_values(event, link_list):
    with scopes_disabled():
        form = MailForm(event=event, data={'subject_0': 'Hi', 'text_0': '{list_link}', 'link_list': link_list.pk})
        form.is_valid()

        assert form.link_list_example() == {'list_link': '[list_link]', 'list_code': '[list_code]'}
