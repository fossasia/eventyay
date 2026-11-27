import json
from datetime import timedelta
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import CartPosition, Product, Question
from eventyay.presale.forms.checkout import ContactForm, QuestionsForm


def _orderforms_url(event) -> str:
    return reverse(
        'control:event.products.orderforms',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


def _reorder_url(event) -> str:
    return reverse(
        'control:event.products.questions.reorder',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


def _post_reorder(client, event, ids: list):
    return client.post(
        _reorder_url(event),
        data=json.dumps({'ids': ids}),
        content_type='application/json',
    )


def _rendered_dnd_sections(client, event) -> tuple[list[str], list[str]]:
    response = client.get(_orderforms_url(event))
    assert response.status_code == 200
    doc = BeautifulSoup(response.content.decode(), 'lxml')
    tbodies = doc.select('tbody[data-dnd-url]')
    assert len(tbodies) == 2
    customer_ids = [row['data-dnd-id'] for row in tbodies[0].select('tr[data-dnd-id]')]
    attendee_ids = [row['data-dnd-id'] for row in tbodies[1].select('tr[data-dnd-id]')]
    return customer_ids, attendee_ids


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_reorder_attendee_fields_preserves_customer_order(organizer_client, event):
    with scope(organizer=event.organizer):
        q = Question.objects.create(event=event, question='Dietary notes', type=Question.TYPE_STRING, position=10)

    customer_order = ['order_phone', 'name_address', 'order_email']
    attendee_order = ['company', 'attendee_name_parts', str(q.pk), 'attendee_email', 'job_title', 'street']

    res = _post_reorder(organizer_client, event, customer_order)
    assert res.status_code == 200

    res = _post_reorder(organizer_client, event, attendee_order)
    assert res.status_code == 200

    event.settings.flush()
    saved_order = event.settings.system_question_order
    assert saved_order['order_phone'] == 0
    assert saved_order['name_address'] == 1
    assert saved_order['order_email'] == 2
    assert saved_order['company'] == 0
    assert saved_order['attendee_name_parts'] == 1
    assert saved_order['attendee_email'] == 3

    with scope(organizer=event.organizer):
        q.refresh_from_db()
        assert q.position == 2

    rendered_customer, rendered_attendee = _rendered_dnd_sections(organizer_client, event)
    assert rendered_customer == customer_order
    assert rendered_attendee == attendee_order

    event.settings.order_email_asked = True
    event.settings.order_phone_asked = True
    request = RequestFactory().get('/')
    request.event = event
    request.session = {}
    contact_form = ContactForm(event=event, request=request)
    assert list(contact_form.fields.keys()).index('phone') < list(contact_form.fields.keys()).index('email')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_reorder_customer_fields_preserves_attendee_and_checkout_order(organizer_client, event):
    with scope(organizer=event.organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=Decimal('10.00'), admission=True)
        q = Question.objects.create(event=event, question='Dietary notes', type=Question.TYPE_STRING, position=10)
        q.products.add(product)
        cart_pos = CartPosition.objects.create(
            event=event,
            product=product,
            price=Decimal('10.00'),
            expires=timezone.now() + timedelta(minutes=15),
        )

    attendee_order = ['street', 'company', str(q.pk), 'attendee_name_parts', 'attendee_email', 'job_title']
    customer_order = ['order_phone', 'order_email', 'name_address']

    assert _post_reorder(organizer_client, event, attendee_order).status_code == 200
    assert _post_reorder(organizer_client, event, customer_order).status_code == 200

    event.settings.flush()
    saved_order = event.settings.system_question_order
    assert saved_order['street'] == 0
    assert saved_order['company'] == 1
    assert saved_order['attendee_name_parts'] == 3
    assert saved_order['order_phone'] == 0
    assert saved_order['order_email'] == 1
    assert saved_order['name_address'] == 2

    rendered_customer, rendered_attendee = _rendered_dnd_sections(organizer_client, event)
    assert rendered_customer == customer_order
    assert rendered_attendee == attendee_order

    event.settings.attendee_names_asked = True
    event.settings.attendee_company_asked = True
    event.settings.attendee_addresses_asked = True
    with scope(organizer=event.organizer):
        q.refresh_from_db()
        assert q.position == 2
        cart_pos.product.questions_to_ask = [q]
        cart_pos.answerlist = []
        questions_form = QuestionsForm(cartpos=cart_pos, event=event)
    field_names = list(questions_form.fields.keys())
    assert field_names.index('street') < field_names.index('company') < field_names.index(f'question_{q.pk}')
    assert field_names.index(f'question_{q.pk}') < field_names.index('attendee_name_parts')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_reorder_custom_questions_only_preserves_system_question_order(organizer_client, event):
    with scope(organizer=event.organizer):
        q1 = Question.objects.create(event=event, question='First', type=Question.TYPE_STRING, position=0)
        q2 = Question.objects.create(event=event, question='Second', type=Question.TYPE_STRING, position=1)

    assert _post_reorder(organizer_client, event, ['order_phone', 'order_email', 'name_address']).status_code == 200
    assert (
        _post_reorder(
            organizer_client,
            event,
            ['company', 'attendee_name_parts', 'attendee_email', 'job_title', 'street', str(q1.pk), str(q2.pk)],
        ).status_code
        == 200
    )

    res = _post_reorder(organizer_client, event, [str(q2.pk), str(q1.pk)])
    assert res.status_code == 200

    event.settings.flush()
    saved_order = event.settings.system_question_order
    assert saved_order['order_phone'] == 0
    assert saved_order['company'] == 0
    assert saved_order['attendee_name_parts'] == 1
    with scope(organizer=event.organizer):
        q1.refresh_from_db()
        q2.refresh_from_db()
        assert (q2.position, q1.position) == (0, 1)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('payload', [{'ids': 'order_email'}, {'ids': [1, 2]}, {'ids': None}])
def test_reorder_questions_rejects_malformed_ids(organizer_client, event, payload):
    res = organizer_client.post(
        _reorder_url(event),
        data=json.dumps(payload),
        content_type='application/json',
    )
    assert res.status_code == 400
