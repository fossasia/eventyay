from types import SimpleNamespace

import pytest
from django.contrib.messages import get_messages
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory
from django_scopes import scope

from eventyay.base.models import InvoiceAddress
from eventyay.presale.checkoutflowstep.questions_step import QuestionsStep


def _questions_step(event, positions=(), cart_session=None):
    request = RequestFactory().get('/')
    request.event = event
    request._messages = CookieStorage(request)
    step = QuestionsStep(event=event)
    step.request = request
    # Stub out the cart lookups so only is_completed() itself is exercised.
    step.__dict__.update(
        cart_session=cart_session if cart_session is not None else {'email': 'buyer@example.org'},
        all_optional=False,
        address_asked=False,
        invoice_address=InvoiceAddress(),
        _positions_for_questions=list(positions),
    )
    return step, request


def _position_with_unanswered_required_question():
    question = SimpleNamespace(id=1, pk=1, required=True, dependency_question_id=None)
    product = SimpleNamespace(questions_to_ask=[question])
    return SimpleNamespace(answerlist=[], product=product)


@pytest.mark.django_db
def test_is_completed_sends_buyer_back_when_a_required_answer_is_missing(event):
    step, request = _questions_step(event, positions=[_position_with_unanswered_required_question()])

    with scope(event=event):
        assert step.is_completed(request, warn=True) is False

    assert [str(m) for m in get_messages(request)] == ['Please fill in answers to all required questions.']


@pytest.mark.django_db
def test_is_completed_warns_when_the_required_email_is_missing(event):
    event.settings.order_email_asked = True
    event.settings.order_email_required = True
    step, request = _questions_step(event, cart_session={})

    with scope(event=event):
        assert step.is_completed(request, warn=True) is False

    assert [str(m) for m in get_messages(request)] == ['Please enter a valid email address.']


@pytest.mark.django_db
def test_is_completed_without_warn_adds_no_invoice_name_message(event):
    event.settings.invoice_name_required = True
    step, request = _questions_step(event)

    with scope(event=event):
        assert step.is_completed(request, warn=False) is False

    assert list(get_messages(request)) == []
