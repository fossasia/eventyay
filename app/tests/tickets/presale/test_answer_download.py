from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.urls import Resolver404, resolve
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import CartPosition, Event, Organizer, Product, Question, QuestionAnswer
from tests.testutils.sessions import get_cart_session_key


@pytest.fixture
@scopes_disabled()
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now() + timedelta(days=30),
        live=True,
        tickets_published=True,
    )


@pytest.fixture
@scopes_disabled()
def cart_answer(client, event):
    product = Product.objects.create(event=event, name='Ticket', default_price=10)
    question = Question.objects.create(event=event, question='Upload', type=Question.TYPE_FILE)
    position = CartPosition.objects.create(
        event=event,
        cart_id=get_cart_session_key(client, event),
        product=product,
        price=10,
        expires=now() + timedelta(minutes=10),
    )
    return QuestionAnswer.objects.create(cartposition=position, question=question, answer='file://')


def url(event, answer_id):
    return f'/{event.organizer.slug}/{event.slug}/cart/answer/{answer_id}/'


@pytest.mark.django_db
def test_non_numeric_id_is_not_found(client, event):
    assert client.get(url(event, 'abc')).status_code == 404


@pytest.mark.django_db
def test_order_non_numeric_id_is_not_found(client, event):
    assert client.get(f'/{event.organizer.slug}/{event.slug}/order/ABCDE/abc123/answer/abc/').status_code == 404


def test_control_route_rejects_non_numeric_id():
    assert resolve('/control/event/dummy/dummy/orders/FOO/answer/12/').url_name == 'event.order.download.answer'
    with pytest.raises(Resolver404):
        resolve('/control/event/dummy/dummy/orders/FOO/answer/abc/')


@pytest.mark.django_db
def test_answer_without_file_is_not_found(client, event, cart_answer):
    assert client.get(url(event, cart_answer.pk)).status_code == 404


@pytest.mark.django_db
def test_answer_with_file_is_downloaded(client, event, cart_answer):
    with scopes_disabled():
        cart_answer.file.save('upload.txt', ContentFile(b'file_content'))
    response = client.get(url(event, cart_answer.pk))
    assert response.status_code == 200
    assert b''.join(response.streaming_content) == b'file_content'
