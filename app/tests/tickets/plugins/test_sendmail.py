import datetime

import pytest
from django.core import mail as djmail
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Checkin,
    Event,
    Product as Item,
    Order,
    OrderPosition,
    Organizer,
    Team,
    User,
)


@pytest.fixture
def event():
    """Returns an event instance"""
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='tests.tickets.testdummy',
    )
    return event


@pytest.fixture
def item(event):
    """Returns an item instance"""
    return Item.objects.create(name='Test item', event=event, default_price=13)


@pytest.fixture
def checkin_list(event):
    """Returns an checkin list instance"""
    return event.checkin_lists.create(name='Test Checkinlist', all_products=True)


@pytest.fixture
def order(item):
    """Returns an order instance"""
    o = Order.objects.create(
        event=item.event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='DUMMY',
        email='dummy@dummy.test',
        datetime=now(),
        locale='en',
    )
    return o


@pytest.fixture
def pos(order, item):
    return OrderPosition.objects.create(order=order, product=item, price=13)


@pytest.fixture
def logged_in_client(client, event):
    """Returns a logged client"""
    user = User.objects.create_superuser('dummy@dummy.dummy', 'dummy')
    t = Team.objects.create(organizer=event.organizer, can_view_orders=True, can_change_orders=True)
    t.members.add(user)
    t.limit_events.add(event)
    client.force_login(user)
    return client


@pytest.fixture
def sendmail_url(event):
    """Returns a url for sendmail"""
    url = '/control/event/{orga}/{event}/sendmail/'.format(
        event=event.slug,
        orga=event.organizer.slug,
    )
    return url


@pytest.mark.django_db
def test_sendmail_view(logged_in_client, sendmail_url, expected=200):
    response = logged_in_client.get(sendmail_url)

    assert response.status_code == expected


@pytest.mark.django_db
def test_sendmail_simple_case(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.product_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [order.email]
    assert djmail.outbox[0].subject == 'Test subject'
    assert 'This is a test file for sending mails.' in djmail.outbox[0].body

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Test subject' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_email_not_sent_if_order_not_match(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'p',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert 'alert-danger' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_preview(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'action': 'preview',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'E-mail preview' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_invalid_data(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
        },
        follow=True,
    )

    assert 'has-error' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_multi_locales(logged_in_client, sendmail_url, event, item):
    djmail.outbox = []

    event.settings.set('locales', ['en', 'de'])

    with scopes_disabled():
        o = Order.objects.create(
            event=item.event,
            status=Order.STATUS_PAID,
            expires=now() + datetime.timedelta(hours=1),
            total=13,
            code='DUMMY',
            email='dummy@dummy.test',
            datetime=now(),
            locale='de',
        )
        OrderPosition.objects.create(order=o, item=item, price=13)

    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'p',
            'recipients': 'orders',
            'items': item.pk,
            'subject_0': 'Test subject',
            'message_0': 'Test message',
            'subject_1': 'Benutzer',
            'message_1': 'Test nachricht',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == [o.email]
    assert djmail.outbox[0].subject == 'Benutzer'
    assert 'Test nachricht' in djmail.outbox[0].body

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Benutzer' in response.rendered_content
    assert 'Test nachricht' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_subevents(logged_in_client, sendmail_url, event, order, pos):
    event.has_subevents = True
    event.save()
    with scopes_disabled():
        se1 = event.subevents.create(name='Subevent FOO', date_from=now())
        se2 = event.subevents.create(name='Bar', date_from=now())
        op = order.positions.last()
    op.subevent = se1
    op.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'subevent': se1.pk,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'subevent': se2.pk,
        },
        follow=True,
    )
    assert len(djmail.outbox) == 0

    url = sendmail_url + 'history/'
    response = logged_in_client.get(url)

    assert response.status_code == 200
    assert 'Subevent FOO' in response.rendered_content


@pytest.mark.django_db
def test_sendmail_placeholder(logged_in_client, sendmail_url, event, order, pos):
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'orders',
            'items': pos.item_id,
            'subject_0': '{code} Test subject',
            'message_0': 'This is a test file for sending mails.',
            'action': 'preview',
        },
        follow=True,
    )

    assert response.status_code == 200
    assert 'F8VVL' in response.rendered_content

    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_sendmail_attendee_mails(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'attendee@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_both_mails(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'attendee@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'both',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ['attendee@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert djmail.outbox[1].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[1].body
    assert '/order/' in djmail.outbox[1].body


@pytest.mark.django_db
def test_sendmail_both_but_same_address(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = 'dummy@dummy.test'
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'both',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[0].body
    assert '/order/' in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_fallback(logged_in_client, sendmail_url, event, order, pos):
    p = pos
    event.settings.attendee_emails_asked = True
    p.attendee_email = None
    p.save()

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['dummy@dummy.test']
    assert '/ticket/' not in djmail.outbox[0].body
    assert '/order/' in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_product_filter(logged_in_client, sendmail_url, event, order, pos):
    event.settings.attendee_emails_asked = True
    with scopes_disabled():
        i2 = Item.objects.create(name='Test item', event=event, default_price=13)
        p = pos
        p.attendee_email = 'attendee1@dummy.test'
        p.save()
        order.positions.create(item=i2, price=0, attendee_email='attendee2@dummy.test')

        djmail.outbox = []
        response = logged_in_client.post(
            sendmail_url,
            {
                'sendto': 'na',
                'recipients': 'attendees',
                'items': i2.pk,
                'subject_0': 'Test subject',
                'message_0': 'This is a test file for sending mails.',
            },
            follow=True,
        )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee2@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body


@pytest.mark.django_db
def test_sendmail_attendee_checkin_filter(logged_in_client, sendmail_url, event, order, checkin_list, item, pos):
    event.settings.attendee_emails_asked = True
    with scopes_disabled():
        chkl2 = event.checkin_lists.create(name='Test Checkinlist 2', all_products=True)
        p = pos
        p.attendee_email = 'attendee1@dummy.test'
        p.save()
        pos2 = order.positions.create(item=item, price=0, attendee_email='attendee2@dummy.test')
        Checkin.objects.create(position=pos2, list=chkl2)

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'filter_checkins': 'on',
            'checkin_lists': [chkl2.id],
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee2@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'filter_checkins': 'on',
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].to == ['attendee1@dummy.test']
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body

    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'filter_checkins': 'on',
            'checkin_lists': [chkl2.id],
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert djmail.outbox[0].to == ['attendee1@dummy.test']
    assert djmail.outbox[1].to == ['attendee2@dummy.test']

    # Test that filtering is ignored if filter_checkins is not set
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'not_checked_in': 'on',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert '/ticket/' in djmail.outbox[1].body
    assert '/order/' not in djmail.outbox[1].body
    to_emails = set(*zip(*[mail.to for mail in djmail.outbox]))
    assert to_emails == {'attendee1@dummy.test', 'attendee2@dummy.test'}

    # Test that filtering is ignored if filter_checkins is not set
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'sendto': 'na',
            'recipients': 'attendees',
            'items': pos2.item_id,
            'subject_0': 'Test subject',
            'message_0': 'This is a test file for sending mails.',
            'checkin_lists': [chkl2.id],
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert len(djmail.outbox) == 2
    assert '/ticket/' in djmail.outbox[0].body
    assert '/order/' not in djmail.outbox[0].body
    assert '/ticket/' in djmail.outbox[1].body
    assert '/order/' not in djmail.outbox[1].body
    to_emails = set(*zip(*[mail.to for mail in djmail.outbox]))
    assert to_emails == {'attendee1@dummy.test', 'attendee2@dummy.test'}

@pytest.mark.django_db
def test_sendmail_save_draft(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.plugins.sendmail.models import EmailQueue
    djmail.outbox = []
    response = logged_in_client.post(
        sendmail_url,
        {
            'order_status': 'na',
            'recipients': 'orders',
            'products': [pos.product_id],
            'subject_0': 'Test draft subject',
            'text_0': 'This is a test draft message.',
            'action': 'draft',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    assert len(djmail.outbox) == 0

    drafts = EmailQueue.objects.filter(event=event, is_draft=True)
    assert drafts.count() == 1
    draft = drafts.first()
    assert draft.subject == 'Test draft subject'
    assert 'This is a test draft message.' in str(draft.message)

    with scopes_disabled():
        assert draft.send() is False
    assert len(djmail.outbox) == 0


@pytest.mark.django_db
def test_edit_draft_without_filters_redirects_to_composer(logged_in_client, event):
    from eventyay.plugins.sendmail.models import EmailQueue

    draft = EmailQueue.objects.create(
        event=event,
        composing_for='attendees',
        subject='Draft without filters',
        message='Message',
        is_draft=True,
    )
    edit_url = reverse(
        'control:event.mail.edit',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'pk': draft.pk,
        },
    )

    response = logged_in_client.get(edit_url)

    assert response.status_code == 302
    assert response.url.endswith(draft.get_edit_url())


@pytest.fixture
def custom_template(event):
    from eventyay.base.i18n import LazyI18nString
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    return TicketMailTemplate.objects.create(
        event=event,
        subject=LazyI18nString({'en': 'Hello {event}'}),
        text=LazyI18nString({'en': 'Dear customer, welcome to {event}.'}),
        reply_to='reply@example.com',
        bcc='bcc@example.com',
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_create(logged_in_client, event):
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    url = reverse(
        'control:event.mail.custom_templates.create',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200

    response = logged_in_client.post(
        url,
        {
            'subject_0': 'Custom subject {event}',
            'text_0': 'Custom body for {event}',
            'reply_to': 'hello@example.com',
            'bcc': '',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert TicketMailTemplate.objects.filter(event=event).count() == 1
    template = TicketMailTemplate.objects.get(event=event)
    assert 'Custom subject' in str(template.subject)
    assert 'Custom body' in str(template.text)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_compose_prefill(logged_in_client, event, custom_template):
    url = reverse(
        'control:event.mail.send',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(f'{url}?template={custom_template.pk}')
    assert response.status_code == 200
    form = response.context['form']
    assert 'Hello' in str(form.initial.get('subject'))
    # MailForm body field is ``text``; also set ``message`` for compatibility.
    assert 'welcome' in str(form.initial.get('message') or '')
    assert 'welcome' in str(form.initial.get('text') or '')
    assert 'welcome' in str(form['text'].value() or '')
    assert form.initial.get('reply_to') == 'reply@example.com'
    assert form.initial.get('bcc') == 'bcc@example.com'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_update(logged_in_client, event, custom_template):
    from eventyay.base.models import LogEntry
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    url = reverse(
        'control:event.mail.custom_templates.edit',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'pk': custom_template.pk,
        },
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert 'Hello' in response.rendered_content

    response = logged_in_client.post(
        url,
        {
            'subject_0': 'Updated subject {event}',
            'text_0': 'Updated body for {event}',
            'reply_to': 'new-reply@example.com',
            'bcc': 'new-bcc@example.com',
        },
        follow=True,
    )
    assert response.status_code == 200
    custom_template.refresh_from_db()
    assert 'Updated subject' in str(custom_template.subject)
    assert 'Updated body' in str(custom_template.text)
    assert custom_template.reply_to == 'new-reply@example.com'
    assert custom_template.bcc == 'new-bcc@example.com'

    log = LogEntry.objects.filter(
        event=event,
        action_type='eventyay.plugins.sendmail.ticket_mail_template.changed',
    ).latest('datetime')
    assert log.parsed_data['id'] == custom_template.pk
    # LazyI18nString fields must be JSON-serializable (dict or str), not raw objects.
    if 'subject' in log.parsed_data:
        assert isinstance(log.parsed_data['subject'], (str, dict))
    if 'text' in log.parsed_data:
        assert isinstance(log.parsed_data['text'], (str, dict))
    assert TicketMailTemplate.objects.filter(pk=custom_template.pk).exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_templates_page_hides_system_edit_without_settings_permission(
    client, event, custom_template
):
    from django.contrib.auth import get_user_model

    from eventyay.base.models import Team

    user = get_user_model().objects.create_user(
        email='orders-only@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=event.organizer,
        name='Orders only',
        all_events=True,
        can_change_orders=True,
        can_change_event_settings=False,
        can_view_orders=True,
    ).members.add(user)
    client.force_login(user)

    url = reverse(
        'control:event.mail.templates',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.rendered_content
    assert 'Custom Mail' in content
    assert 'Placed order' in content
    system_edit_url = reverse(
        'control:event.mail.templates.system',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'template_key': 'order_placed',
        },
    )
    assert system_edit_url not in content


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_custom_template_delete(logged_in_client, event, custom_template):
    from eventyay.plugins.sendmail.models import TicketMailTemplate

    url = reverse(
        'control:event.mail.custom_templates.delete',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'pk': custom_template.pk,
        },
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200

    response = logged_in_client.post(url, follow=True)
    assert response.status_code == 200
    assert not TicketMailTemplate.objects.filter(pk=custom_template.pk).exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_templates_page_lists_custom_templates(logged_in_client, event, custom_template):
    url = reverse(
        'control:event.mail.templates',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert 'Hello' in response.rendered_content
    assert 'New custom template' in response.rendered_content
    assert 'Custom Mail' in response.rendered_content
    assert 'Placed order' in response.rendered_content


@pytest.mark.django_db
def test_ticket_mail_template_form_validates_reply_to_and_bcc(event):
    from eventyay.plugins.sendmail.forms import TicketMailTemplateForm

    invalid = TicketMailTemplateForm(
        data={
            'subject_0': 'Subject',
            'text_0': 'Body',
            'reply_to': 'not-an-email',
            'bcc': 'ok@example.com, bad-address',
        },
        event=event,
    )
    assert not invalid.is_valid()
    assert 'reply_to' in invalid.errors
    assert 'bcc' in invalid.errors

    valid = TicketMailTemplateForm(
        data={
            'subject_0': 'Subject',
            'text_0': 'Body',
            'reply_to': 'hello@example.com',
            'bcc': 'a@example.com, b@example.com',
        },
        event=event,
    )
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['bcc'] == 'a@example.com, b@example.com'


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_allowed_records_usage(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.base.signals import entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Allowed test subject',
                'text_0': 'Message for outbox.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content

        queue = EmailQueue.objects.filter(event=event, is_draft=False).first()
        assert queue is not None
        assert str(queue.subject) == 'Allowed test subject'

        assert len(usage_events) == 1
        sender, kwargs = usage_events[0]
        assert sender == event.organizer
        assert kwargs['capability'] == 'email.bulk.monthly'
        assert kwargs['quantity'] == 1
        assert kwargs['unit'] == 'emails'
        assert kwargs['source_type'] == 'ticket_bulk_email'
        assert kwargs['source_id'] == str(queue.pk)
        assert kwargs['idempotency_key'] == f'ticket_bulk_mail_{queue.pk}'
        assert kwargs['event'] == event
    finally:
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_denied_by_entitlement(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.base.entitlements import EntitlementDecision
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    def on_check(sender, capability, **kwargs):
        if capability == 'email.bulk.monthly':
            return EntitlementDecision(
                allowed=False,
                reason_code='limit_reached',
                message='Monthly bulk email quota exceeded for plan.',
            )
        return EntitlementDecision(allowed=True)

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Denied test subject',
                'text_0': 'This message should not be sent.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'Monthly bulk email quota exceeded for plan.' in response.rendered_content
        # Ensure temporary queue item was cleaned up and not saved to outbox
        assert EmailQueue.objects.filter(event=event).count() == 0
        assert len(usage_events) == 0
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_unique_recipient_deduplication(logged_in_client, sendmail_url, event, order, pos, item):
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    # Create a second order with the same email address in UPPERCASE
    order2 = Order.objects.create(
        event=item.event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='DUMMY2',
        email=order.email.upper(),
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=order2, product=item, price=13)

    check_quantities = []

    def on_check(sender, capability, quantity=1, **kwargs):
        if capability == 'email.bulk.monthly':
            check_quantities.append(quantity)
        return None

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Deduplication test',
                'text_0': 'Testing deduplicated recipients.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content

        queue = EmailQueue.objects.filter(event=event, is_draft=False).first()
        assert queue is not None
        assert queue.get_recipient_emails() == [order.email.lower()]

        # 2 orders but only 1 unique recipient
        assert check_quantities == [1]
        assert len(usage_events) == 1
        assert usage_events[0][1]['quantity'] == 1
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_draft_and_test_exempt(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.base.entitlements import EntitlementDecision
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    check_calls = []

    def on_check(sender, capability, **kwargs):
        check_calls.append((sender, capability, kwargs))
        if capability == 'email.bulk.monthly':
            return EntitlementDecision(allowed=False, message='Should not trigger for draft or test')
        return EntitlementDecision(allowed=True)

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        # 1. Draft save should be exempt
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Draft subject',
                'text_0': 'Draft message.',
                'action': 'draft',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content
        draft = EmailQueue.objects.filter(event=event, is_draft=True).first()
        assert draft is not None
        assert len(check_calls) == 0
        assert len(usage_events) == 0

        # 2. Preview should be exempt
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Preview subject',
                'text_0': 'Preview message.',
                'action': 'preview',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert len(check_calls) == 0
        assert len(usage_events) == 0

        # 3. Single test email should be exempt
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Test email subject',
                'text_0': 'Test email message.',
                'test_email': 'testpreview@example.com',
                'action': 'test',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content
        assert len(check_calls) == 0
        assert len(usage_events) == 0
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_preserve_existing_draft_on_denial(logged_in_client, sendmail_url, event, order, pos):
    from eventyay.base.entitlements import EntitlementDecision
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter

    # Create an existing draft
    draft = EmailQueue.objects.create(
        event=event,
        composing_for=ComposingFor.ATTENDEES,
        subject='Existing Draft Subject',
        message='Existing Draft Message',
        is_draft=True,
    )
    EmailQueueFilter.objects.create(
        mail=draft,
        recipients='orders',
        order_status=['na'],
        orders=[order.pk],
        products=[pos.product_id],
    )

    def on_check(sender, capability, **kwargs):
        if capability == 'email.bulk.monthly':
            return EntitlementDecision(
                allowed=False,
                reason_code='limit_reached',
                message='Quota denied for sending.',
            )
        return EntitlementDecision(allowed=True)

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        # User attempts to send the draft to outbox
        response = logged_in_client.post(
            sendmail_url,
            {
                'draft_id': draft.pk,
                'order_status': 'na',
                'recipients': 'orders',
                'products': [pos.product_id],
                'subject_0': 'Updated Draft Subject',
                'text_0': 'Updated Draft Message',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'Quota denied for sending.' in response.rendered_content

        # Verify draft was NOT deleted and remains marked as draft
        draft.refresh_from_db()
        assert draft.is_draft is True
        assert str(draft.subject) == 'Updated Draft Subject'
        assert len(usage_events) == 0
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_teams_entitlement_and_deduplication(logged_in_client, event):
    from eventyay.base.entitlements import EntitlementDecision
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue

    # Create 1 user in 2 teams to verify recipient deduplication across teams
    u1 = User.objects.create(email='colleague@example.com')
    team1 = Team.objects.create(organizer=event.organizer, name='Operations', can_view_orders=True)
    team2 = Team.objects.create(organizer=event.organizer, name='Logistics', can_view_orders=True)
    team1.members.add(u1)
    team2.members.add(u1)

    compose_teams_url = reverse(
        'control:event.mail.compose_teams',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    # 1. Test denial
    def on_check_deny(sender, capability, **kwargs):
        if capability == 'email.bulk.monthly':
            return EntitlementDecision(allowed=False, message='Team email monthly quota exceeded')
        return EntitlementDecision(allowed=True)

    entitlement_check.connect(on_check_deny)
    try:
        response = logged_in_client.post(
            compose_teams_url,
            {
                'teams': [team1.pk, team2.pk],
                'subject_0': 'Team Update',
                'message_0': 'Important team update message.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'Team email monthly quota exceeded' in response.rendered_content
        assert EmailQueue.objects.filter(event=event, composing_for=ComposingFor.TEAMS).count() == 0
    finally:
        entitlement_check.disconnect(on_check_deny)

    # 2. Test allowed with recipient deduplication
    check_quantities = []

    def on_check_allow(sender, capability, quantity=1, **kwargs):
        if capability == 'email.bulk.monthly':
            check_quantities.append(quantity)
        return None

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check_allow)
    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            compose_teams_url,
            {
                'teams': [team1.pk, team2.pk],
                'subject_0': 'Team Update Allowed',
                'message_0': 'Important team update message.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content

        queue = EmailQueue.objects.filter(event=event, composing_for=ComposingFor.TEAMS, is_draft=False).first()
        assert queue is not None
        assert queue.get_recipient_emails() == ['colleague@example.com']

        # User was in 2 selected teams but deduplicated to 1 unique recipient
        assert check_quantities == [1]
        assert len(usage_events) == 1
        assert usage_events[0][1]['quantity'] == 1
        assert usage_events[0][1]['source_type'] == 'ticket_bulk_email'
        assert usage_events[0][1]['source_id'] == str(queue.pk)
        assert usage_events[0][1]['idempotency_key'] == f'ticket_bulk_mail_{queue.pk}'
    finally:
        entitlement_check.disconnect(on_check_allow)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_teams_preserve_existing_draft_on_denial(logged_in_client, event):
    from eventyay.base.entitlements import EntitlementDecision
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter

    u = User.objects.create(email='crew@example.com')
    team = Team.objects.create(organizer=event.organizer, name='Crew', can_view_orders=True)
    team.members.add(u)

    draft = EmailQueue.objects.create(
        event=event,
        composing_for=ComposingFor.TEAMS,
        subject='Team Draft Subject',
        message='Team Draft Message',
        is_draft=True,
    )
    EmailQueueFilter.objects.create(
        mail=draft,
        teams=[team.pk],
    )

    compose_teams_url = reverse(
        'control:event.mail.compose_teams',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    def on_check(sender, capability, **kwargs):
        if capability == 'email.bulk.monthly':
            return EntitlementDecision(allowed=False, message='Quota denied for team mail.')
        return EntitlementDecision(allowed=True)

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            compose_teams_url,
            {
                'draft_id': draft.pk,
                'teams': [team.pk],
                'subject_0': 'Updated Team Draft Subject',
                'message_0': 'Updated Team Draft Message',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'Quota denied for team mail.' in response.rendered_content

        draft.refresh_from_db()
        assert draft.is_draft is True
        assert str(draft.subject) == 'Updated Team Draft Subject'
        assert len(usage_events) == 0
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_attendee_whitespace_only_recipients_rejected(logged_in_client, sendmail_url, event, item):
    from eventyay.base.signals import entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    event.settings.attendee_emails_asked = True

    order_blank = Order.objects.create(
        event=event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='BLANK1',
        email='   ',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=order_blank, product=item, price=13, attendee_email='   ')

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'both',
                'products': [item.pk],
                'subject_0': 'Blank recipient test',
                'text_0': 'Testing blank recipients rejection.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'There are no valid email addresses for the selected recipients.' in response.rendered_content
        assert EmailQueue.objects.filter(event=event, is_draft=False).count() == 0
        assert len(usage_events) == 0
    finally:
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_team_whitespace_only_recipients_rejected(logged_in_client, event):
    from eventyay.base.signals import entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    u_blank = User.objects.create(email='   ')
    team = Team.objects.create(organizer=event.organizer, name='BlankTeam', can_view_orders=True)
    team.members.add(u_blank)

    compose_teams_url = reverse(
        'control:event.mail.compose_teams',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            compose_teams_url,
            {
                'teams': [team.pk],
                'subject_0': 'Blank team recipient test',
                'message_0': 'Testing blank team recipients rejection.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'There are no valid recipients for the selected teams.' in response.rendered_content
        assert EmailQueue.objects.filter(event=event, is_draft=False).count() == 0
        assert len(usage_events) == 0
    finally:
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_mixed_recipients_whitespace_and_duplicates(logged_in_client, sendmail_url, event, item):
    from eventyay.base.signals import entitlement_check, entitlement_usage_recorded
    from eventyay.plugins.sendmail.models import EmailQueue

    event.settings.attendee_emails_asked = True

    o1 = Order.objects.create(
        event=event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='MIX1',
        email='valid1@example.com',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=o1, product=item, price=13)

    o2 = Order.objects.create(
        event=event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='MIX2',
        email='   ',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=o2, product=item, price=13, attendee_email='   ')

    o3 = Order.objects.create(
        event=event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='MIX3',
        email='VALID1@EXAMPLE.COM',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=o3, product=item, price=13)

    o4 = Order.objects.create(
        event=event,
        status=Order.STATUS_PENDING,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code='MIX4',
        email='valid2@example.com',
        datetime=now(),
        locale='en',
    )
    OrderPosition.objects.create(order=o4, product=item, price=13)

    checked_quantities = []

    def on_check(sender, capability, quantity=1, **kwargs):
        if capability == 'email.bulk.monthly':
            checked_quantities.append(quantity)
        return None

    usage_events = []

    def on_usage(sender, **kwargs):
        usage_events.append((sender, kwargs))

    entitlement_check.connect(on_check)
    entitlement_usage_recorded.connect(on_usage)
    try:
        response = logged_in_client.post(
            sendmail_url,
            {
                'order_status': 'na',
                'recipients': 'both',
                'products': [item.pk],
                'subject_0': 'Mixed recipient test',
                'text_0': 'Testing mixed recipients counting.',
            },
            follow=True,
        )
        assert response.status_code == 200
        assert 'alert-success' in response.rendered_content

        queue = EmailQueue.objects.filter(event=event, is_draft=False).first()
        assert queue is not None
        assert queue.get_recipient_emails() == ['valid1@example.com', 'valid2@example.com']
        assert not queue.recipients.filter(email='').exists()
        assert not queue.recipients.filter(email='   ').exists()

        assert checked_quantities == [2]
        assert len(usage_events) == 1
        assert usage_events[0][1]['quantity'] == 2
    finally:
        entitlement_check.disconnect(on_check)
        entitlement_usage_recorded.disconnect(on_usage)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_attendee_serializes_with_organizer_select_for_update(logged_in_client, sendmail_url, event, order, pos, monkeypatch):
    from eventyay.base.models.organizer import Organizer

    locked_organizers = []
    real_select_for_update = Organizer.objects.select_for_update

    def spy_select_for_update(*args, **kwargs):
        qs = real_select_for_update(*args, **kwargs)
        real_filter = qs.filter

        def spy_filter(*f_args, **f_kwargs):
            if 'pk' in f_kwargs:
                locked_organizers.append(f_kwargs['pk'])
            return real_filter(*f_args, **f_kwargs)

        qs.filter = spy_filter
        return qs

    monkeypatch.setattr(Organizer.objects, 'select_for_update', spy_select_for_update)

    response = logged_in_client.post(
        sendmail_url,
        {
            'order_status': 'na',
            'recipients': 'orders',
            'products': [pos.product_id],
            'subject_0': 'Locking test subject',
            'text_0': 'Testing organizer lock serialization.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert locked_organizers == [event.organizer_id]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_team_serializes_with_organizer_select_for_update(logged_in_client, event, monkeypatch):
    from eventyay.base.models.organizer import Organizer

    u = User.objects.create(email='crew_lock@example.com')
    team = Team.objects.create(organizer=event.organizer, name='LockCrew', can_view_orders=True)
    team.members.add(u)

    compose_teams_url = reverse(
        'control:event.mail.compose_teams',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    locked_organizers = []
    real_select_for_update = Organizer.objects.select_for_update

    def spy_select_for_update(*args, **kwargs):
        qs = real_select_for_update(*args, **kwargs)
        real_filter = qs.filter

        def spy_filter(*f_args, **f_kwargs):
            if 'pk' in f_kwargs:
                locked_organizers.append(f_kwargs['pk'])
            return real_filter(*f_args, **f_kwargs)

        qs.filter = spy_filter
        return qs

    monkeypatch.setattr(Organizer.objects, 'select_for_update', spy_select_for_update)

    response = logged_in_client.post(
        compose_teams_url,
        {
            'teams': [team.pk],
            'subject_0': 'Team Lock Subject',
            'message_0': 'Testing team organizer lock.',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content
    assert locked_organizers == [event.organizer_id]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_attendee_draft_to_outbox_logs_enqueue_event(logged_in_client, sendmail_url, event, order, pos, monkeypatch):
    from eventyay.base.operational_logging import OUTCOME_SUCCESS
    from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter

    draft = EmailQueue.objects.create(
        event=event,
        composing_for=ComposingFor.ATTENDEES,
        subject='Draft Subject to Enqueue',
        message='Draft Message to Enqueue',
        is_draft=True,
    )
    EmailQueueFilter.objects.create(
        mail=draft,
        recipients='orders',
        order_status=['na'],
        orders=[order.pk],
        products=[pos.product_id],
    )

    logged_events = []

    def spy_log_event(component, action, outcome, **kwargs):
        logged_events.append({
            'component': component,
            'action': action,
            'outcome': outcome,
            'kwargs': kwargs,
        })

    monkeypatch.setattr('eventyay.plugins.sendmail.views.log_event', spy_log_event)

    response = logged_in_client.post(
        sendmail_url,
        {
            'draft_id': draft.pk,
            'order_status': 'na',
            'recipients': 'orders',
            'products': [pos.product_id],
            'subject_0': 'Sending Draft Subject',
            'text_0': 'Sending Draft Message',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    draft.refresh_from_db()
    assert draft.is_draft is False

    enqueue_events = [e for e in logged_events if e['action'] == 'mail.enqueue']
    assert len(enqueue_events) == 1
    assert enqueue_events[0]['component'] == 'mail'
    assert enqueue_events[0]['outcome'] == OUTCOME_SUCCESS
    assert enqueue_events[0]['kwargs']['event_id'] == event.pk
    assert enqueue_events[0]['kwargs']['object_id'] == draft.pk


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sendmail_team_draft_to_outbox_logs_enqueue_event(logged_in_client, event, monkeypatch):
    from eventyay.base.operational_logging import OUTCOME_SUCCESS
    from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueFilter

    u = User.objects.create(email='teammate_log@example.com')
    team = Team.objects.create(organizer=event.organizer, name='LogCrew', can_view_orders=True)
    team.members.add(u)

    draft = EmailQueue.objects.create(
        event=event,
        composing_for=ComposingFor.TEAMS,
        subject='Team Draft Subject to Enqueue',
        message='Team Draft Message to Enqueue',
        is_draft=True,
    )
    EmailQueueFilter.objects.create(
        mail=draft,
        teams=[team.pk],
    )

    compose_teams_url = reverse(
        'control:event.mail.compose_teams',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    logged_events = []

    def spy_log_event(component, action, outcome, **kwargs):
        logged_events.append({
            'component': component,
            'action': action,
            'outcome': outcome,
            'kwargs': kwargs,
        })

    monkeypatch.setattr('eventyay.plugins.sendmail.views.log_event', spy_log_event)

    response = logged_in_client.post(
        compose_teams_url,
        {
            'draft_id': draft.pk,
            'teams': [team.pk],
            'subject_0': 'Sending Team Draft Subject',
            'message_0': 'Sending Team Draft Message',
        },
        follow=True,
    )
    assert response.status_code == 200
    assert 'alert-success' in response.rendered_content

    draft.refresh_from_db()
    assert draft.is_draft is False

    enqueue_events = [e for e in logged_events if e['action'] == 'mail.enqueue']
    assert len(enqueue_events) == 1
    assert enqueue_events[0]['component'] == 'mail'
    assert enqueue_events[0]['outcome'] == OUTCOME_SUCCESS
    assert enqueue_events[0]['kwargs']['event_id'] == event.pk
    assert enqueue_events[0]['kwargs']['object_id'] == draft.pk
