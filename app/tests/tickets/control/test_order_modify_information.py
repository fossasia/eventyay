import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.test import TestCase, override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    InvoiceAddress,
    LogEntry,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Question,
    QuestionAnswer,
    Team,
    User,
)


@pytest.fixture
@scopes_disabled()
def modify_env():
    mail.outbox.clear()
    organizer = Organizer.objects.create(name='Dummy Org', slug='dummy-org')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy Event',
        slug='dummy-event',
        date_from=now() + datetime.timedelta(days=30),
        plugins='eventyay.plugins.banktransfer',
        live=True,
        tickets_published=True,
    )
    event.settings.invoice_address_asked = True
    event.settings.invoice_address_required = True
    event.settings.attendee_names_asked = True
    event.settings.attendee_emails_asked = True
    event.settings.attendee_company_asked = True

    user = User.objects.create_user('admin@dummy.dummy', 'dummy')
    team = Team.objects.create(
        organizer=organizer,
        can_view_orders=True,
        can_change_orders=True,
    )
    team.members.add(user)
    team.limit_events.add(event)

    product = Product.objects.create(
        event=event,
        name='Ticket',
        default_price=Decimal('25.00'),
        admission=True,
    )

    q_choice = Question.objects.create(
        event=event,
        question='T-Shirt Size',
        type=Question.TYPE_CHOICE,
        required=True,
    )
    opt_s = q_choice.options.create(answer='S')
    opt_m = q_choice.options.create(answer='M')
    product.questions.add(q_choice)

    order = Order.objects.create(
        code='MOD1',
        event=event,
        email='customer@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now() - datetime.timedelta(days=1),
        expires=now() + datetime.timedelta(days=10),
        total=Decimal('50.00'),
    )

    inv_addr = InvoiceAddress.objects.create(
        order=order,
        is_business=False,
        name_parts={'full_name': 'Original Invoicee', '_scheme': 'full'},
        street='Original Street 1',
        zipcode='12345',
        city='Original City',
        country='DE',
    )

    pos1 = OrderPosition.objects.create(
        order=order,
        positionid=1,
        product=product,
        price=Decimal('25.00'),
        attendee_name_parts={'full_name': 'Original Attendee 1', '_scheme': 'full'},
        attendee_email='att1@dummy.test',
        company='Original Company 1',
    )
    ans1 = QuestionAnswer.objects.create(
        orderposition=pos1,
        question=q_choice,
        answer='S',
    )
    ans1.options.add(opt_s)

    pos2 = OrderPosition.objects.create(
        order=order,
        positionid=2,
        product=product,
        price=Decimal('25.00'),
        attendee_name_parts={'full_name': 'Original Attendee 2', '_scheme': 'full'},
        attendee_email='att2@dummy.test',
        company='Original Company 2',
    )
    ans2 = QuestionAnswer.objects.create(
        orderposition=pos2,
        question=q_choice,
        answer='M',
    )
    ans2.options.add(opt_m)

    return {
        'organizer': organizer,
        'event': event,
        'user': user,
        'product': product,
        'question': q_choice,
        'opt_s': opt_s,
        'opt_m': opt_m,
        'order': order,
        'inv_addr': inv_addr,
        'pos1': pos1,
        'pos2': pos2,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_valid_submission_saves_all_changes(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    with TestCase.captureOnCommitCallbacks(execute=True):
        response = client.post(url, data, follow=False)
    assert response.status_code == 302
    assert response['Location'].endswith(f"/orders/{env['order'].code}/")

    with scopes_disabled():
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'New Invoicee'
        assert env['inv_addr'].street == 'New Street 42'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Updated Attendee 1'
        assert env['pos1'].attendee_email == 'updated1@dummy.test'
        assert env['pos1'].company == 'Updated Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'M'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Updated Attendee 2'
        assert env['pos2'].attendee_email == 'updated2@dummy.test'
        assert env['pos2'].company == 'Updated Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'S'

        assert LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 1
        assert 'Your order has been changed' in mail.outbox[0].subject


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_invalid_invoice_form_preserves_all_attendee_and_order_info(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # country='INVALID' makes invoice_form invalid
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'INVALID',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200

    with scopes_disabled():
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_invalid_attendee_form_prevents_partial_changes(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # pos1 has invalid email
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'invalid-email',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'updated2@dummy.test',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200

    with scopes_disabled():
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_multiple_positions_one_invalid_leaves_no_positions_updated(client, modify_env):
    env = modify_env
    client.force_login(env['user'])

    url = f"/control/event/{env['organizer'].slug}/{env['event'].slug}/orders/{env['order'].code}/info"
    # pos1 is valid, but pos2 has invalid email format
    data = {
        'name_parts_0': 'New Invoicee',
        'street': 'New Street 42',
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Updated Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'updated1@dummy.test',
        f"{env['pos1'].pk}-company": 'Updated Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
        f"{env['pos2'].pk}-attendee_name_parts_0": 'Updated Attendee 2',
        f"{env['pos2'].pk}-attendee_email": 'invalid-email-pos2',
        f"{env['pos2'].pk}-company": 'Updated Company 2',
        f"{env['pos2'].pk}-question_{env['question'].pk}": env['opt_s'].identifier,
        'other-notify': 'on',
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200

    with scopes_disabled():
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'

        env['pos1'].refresh_from_db()
        # pos1 MUST NOT be updated even though pos1's form itself was valid!
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        env['pos2'].refresh_from_db()
        assert env['pos2'].attendee_name == 'Original Attendee 2'
        assert env['pos2'].attendee_email == 'att2@dummy.test'
        assert env['pos2'].company == 'Original Company 2'
        assert env['pos2'].answers.get(question=env['question']).answer == 'M'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()

        assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_presale_order_modify_invalid_invoice_leaves_attendee_info_unchanged(client, modify_env):
    env = modify_env
    # For presale modify, user must be authenticated as order owner
    client.force_login(env['user'])
    with scopes_disabled():
        env['order'].email = env['user'].email
        env['order'].save()

    url = f"/{env['organizer'].slug}/{env['event'].slug}/order/{env['order'].code}/{env['order'].secret}/modify"

    data = {
        'name_parts_0': 'New Presale Invoicee',
        'street': '',  # invalid because invoice_address_required is True
        'zipcode': '54321',
        'city': 'New City',
        'country': 'DE',
        f"{env['pos1'].pk}-attendee_name_parts_0": 'Presale Attendee 1',
        f"{env['pos1'].pk}-attendee_email": 'presale1@dummy.test',
        f"{env['pos1'].pk}-company": 'Presale Company 1',
        f"{env['pos1'].pk}-question_{env['question'].pk}": env['opt_m'].identifier,
    }

    response = client.post(url, data, follow=False)
    assert response.status_code == 200

    with scopes_disabled():
        env['inv_addr'].refresh_from_db()
        assert env['inv_addr'].name == 'Original Invoicee'
        assert env['inv_addr'].street == 'Original Street 1'

        env['pos1'].refresh_from_db()
        assert env['pos1'].attendee_name == 'Original Attendee 1'
        assert env['pos1'].attendee_email == 'att1@dummy.test'
        assert env['pos1'].company == 'Original Company 1'
        assert env['pos1'].answers.get(question=env['question']).answer == 'S'

        assert not LogEntry.objects.filter(
            content_type__model='order',
            object_id=env['order'].pk,
            action_type='eventyay.event.order.modified',
        ).exists()
