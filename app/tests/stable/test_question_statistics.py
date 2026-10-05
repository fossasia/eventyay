from datetime import timedelta
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.test import override_settings
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import Order, OrderPosition, Product, Question, QuestionAnswer


def create_answer(event, question, product, answer, code, status=Order.STATUS_PAID):
    order = Order.objects.create(
        event=event,
        code=code,
        email='buyer@example.org',
        status=status,
        datetime=timezone.now(),
        expires=timezone.now() + timedelta(days=1),
        total=10,
        locale='en',
    )
    position = OrderPosition.objects.create(
        order=order, product=product, price=Decimal('10'), canceled=status == Order.STATUS_CANCELED
    )
    QuestionAnswer.objects.create(orderposition=position, question=question, answer=answer)


@pytest.fixture
def answered_question(event):
    with scope(organizer=event.organizer, event=event):
        ticket = Product.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        workshop = Product.objects.create(event=event, name='Workshop', default_price=5, admission=False)
        question = Question.objects.create(event=event, question='Company', type=Question.TYPE_STRING)
        question.products.add(ticket, workshop)
        create_answer(event, question, ticket, 'ACME Corp', 'FOO')
        create_answer(event, question, workshop, 'Globex', 'BAR')
    return question, ticket, workshop


def statistics_url(event, question):
    return f'/control/event/{event.organizer.slug}/{event.slug}/questions/{question.pk}/'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_question_statistics_filter_by_product(organizer_client, event, answered_question):
    question, ticket, workshop = answered_question
    url = statistics_url(event, question)

    content = organizer_client.get(f'{url}?product={ticket.pk}').content.decode()
    assert 'ACME Corp' in content
    assert 'Globex' not in content

    content = organizer_client.get(f'{url}?product={workshop.pk}').content.decode()
    assert 'Globex' in content
    assert 'ACME Corp' not in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_question_statistics_keeps_product_in_filter_and_links(organizer_client, event, answered_question):
    question, ticket, _workshop = answered_question

    response = organizer_client.get(f'{statistics_url(event, question)}?product={ticket.pk}')
    doc = BeautifulSoup(response.content.decode(), 'lxml')

    select = doc.find('select', attrs={'name': 'product'})
    assert select.find('option', selected=True)['value'] == str(ticket.pk)
    answer_link = doc.select_one('#question-stats a[href*="/orders/"]')
    assert f'product={ticket.pk}' in answer_link['href']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_question_statistics_answer_link_finds_canceled_orders(organizer_client, event, answered_question):
    question, ticket, _workshop = answered_question
    with scope(organizer=event.organizer, event=event):
        create_answer(event, question, ticket, 'Initech', 'BAZ', status=Order.STATUS_CANCELED)

    response = organizer_client.get(f'{statistics_url(event, question)}?status=c&product={ticket.pk}')
    doc = BeautifulSoup(response.content.decode(), 'lxml')
    answer_link = doc.select_one('#question-stats a[href*="/orders/"]')

    assert 'BAZ' in organizer_client.get(answer_link['href']).content.decode()
