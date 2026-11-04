import datetime

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


def _url(event, name, link_list):
    suffix = {'rows': 'rows/', 'unused': 'unused/delete/', 'assignments': 'assignments.csv'}[name]
    return f'/control/event/{event.organizer.slug}/{event.slug}/sendmail/link-lists/{link_list.pk}/{suffix}'


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


@pytest.mark.django_db
def test_sending_gives_each_recipient_their_row(event, order, link_list):
    djmail.outbox = []
    with scopes_disabled():
        queued = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject={'en': 'Your discount'},
            message={'en': 'Use {list_link} with code {list_code}'},
            link_list=link_list,
        )
        for email in ('ali@example.com', 'sara@example.com', 'john@example.com'):
            EmailQueueToUser.objects.create(mail=queued, email=email, orders=[order.pk])

        queued.send(async_send=False)
        unsent = list(queued.recipients.filter(sent=False))

    sent_links = ('https://p.test/a', 'https://p.test/b')
    links = sorted(link for message in djmail.outbox for link in sent_links if link in message.body)
    assert len(djmail.outbox) == 2
    assert links == ['https://p.test/a', 'https://p.test/b']
    assert len(unsent) == 1 and unsent[0].error


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
def test_dialog_adds_rows_and_deletes_only_unused_ones(logged_in_client, event, link_list):
    with scopes_disabled():
        link_list.assign('ali@example.com')

    added = logged_in_client.post(
        _url(event, 'rows', link_list), {'file': _csv('link,code\nhttps://p.test/c,C3\nhttps://p.test/a,A1\n')}
    )
    deleted = logged_in_client.post(_url(event, 'unused', link_list))

    assert added.json() == {'total': 3, 'used': 1, 'left': 2, 'added': 1, 'skipped': 1}
    assert deleted.json() == {'total': 1, 'used': 1, 'left': 0, 'deleted': 2}


@pytest.mark.django_db
def test_assignments_download_lists_who_got_which_row(logged_in_client, event, link_list):
    with scopes_disabled():
        link_list.assign('ali@example.com')

    response = logged_in_client.get(_url(event, 'assignments', link_list))
    lines = response.content.decode().splitlines()

    assert lines[0] == 'link,code,email,assigned_at'
    assert lines[1].startswith('https://p.test/a,A1,ali@example.com,')
    assert lines[2] == 'https://p.test/b,B2,,'


@pytest.mark.django_db
def test_lists_belong_to_their_event(logged_in_client, event, link_list):
    other_event = Event.objects.create(
        organizer=event.organizer, name='Other', slug='other', date_from=now(), plugins='tests.tickets.testdummy'
    )
    with scopes_disabled():
        foreign = MailLinkList.objects.create(event=other_event, name='Other', columns=['link'])

    response = logged_in_client.get(_url(event, 'assignments', foreign))

    assert response.status_code == 404
