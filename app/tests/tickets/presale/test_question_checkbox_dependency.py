from datetime import datetime, timedelta, timezone

import pytest
from django_scopes import scopes_disabled

from eventyay.base.forms.questions import BaseQuestionsForm
from eventyay.base.models import (
    CartPosition,
    Event,
    Organizer,
    Product,
    Question,
    Quota,
)


@pytest.fixture
def env(db):
    with scopes_disabled():
        orga = Organizer.objects.create(name='Org', slug='org')
        event = Event.objects.create(
            organizer=orga,
            name='Conf',
            slug='conf',
            date_from=datetime(2030, 12, 26, tzinfo=timezone.utc),
            plugins='eventyay.plugins.banktransfer',
        )
        product = Product.objects.create(
            event=event,
            name='Ticket',
            default_price=0,
            admission=True,
        )
        quota = Quota.objects.create(event=event, name='Quota', size=200)
        quota.products.add(product)
        cp = CartPosition.objects.create(
            event=event,
            cart_id='test-cart',
            product=product,
            price=0,
            expires=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    return {'event': event, 'product': product, 'cart': cp}


def _add_to_ask(product, *questions):
    """Mimic the ``questions_to_ask`` prefetch attribute expected by the form."""
    product.questions_to_ask = list(questions)


def _build_form(env, data):
    prefix = str(env['cart'].id)
    payload = {f'{prefix}-{k}': v for k, v in data.items()}
    return BaseQuestionsForm(
        data=payload,
        event=env['event'],
        cartpos=env['cart'],
        all_optional=False,
        prefix=prefix,
    )


@pytest.mark.django_db
def test_boolean_checked_makes_followup_required(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='I have dietary restrictions',
            type=Question.TYPE_BOOLEAN,
            required=False,
        )
        child = env['event'].questions.create(
            question='Please describe',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['True'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {f'question_{parent.id}': 'on'})
    assert not form.is_valid()
    assert f'question_{child.id}' in form.errors


@pytest.mark.django_db
def test_boolean_checked_followup_provided_passes(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='I have dietary restrictions',
            type=Question.TYPE_BOOLEAN,
            required=False,
        )
        child = env['event'].questions.create(
            question='Please describe',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['True'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(
        env,
        {
            f'question_{parent.id}': 'on',
            f'question_{child.id}': 'No nuts please',
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_boolean_unchecked_followup_not_required(env):
    """A hidden required follow-up must not block submission."""
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='I have dietary restrictions',
            type=Question.TYPE_BOOLEAN,
            required=False,
        )
        child = env['event'].questions.create(
            question='Please describe',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['True'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_boolean_inverse_dependency_unchecked_requires_followup(env):
    """dependency_values=['False'] means follow-up is shown when the parent is unchecked."""
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='I have already shared this info',
            type=Question.TYPE_BOOLEAN,
            required=False,
        )
        child = env['event'].questions.create(
            question='How should we contact you?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['False'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {})
    assert not form.is_valid()
    assert f'question_{child.id}' in form.errors


@pytest.mark.django_db
def test_boolean_inverse_dependency_checked_skips_followup(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='I have already shared this info',
            type=Question.TYPE_BOOLEAN,
            required=False,
        )
        child = env['event'].questions.create(
            question='How should we contact you?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['False'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {f'question_{parent.id}': 'on'})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multi_checkbox_matching_option_requires_followup(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='Which workshops?',
            type=Question.TYPE_CHOICE_MULTIPLE,
            required=False,
        )
        parent.options.create(answer='Workshop A', identifier='WSA')
        parent.options.create(answer='Workshop B', identifier='WSB')
        child = env['event'].questions.create(
            question='Workshop A: prior experience?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['WSA'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {f'question_{parent.id}': ['WSA']})
    assert not form.is_valid()
    assert f'question_{child.id}' in form.errors


@pytest.mark.django_db
def test_multi_checkbox_matching_option_followup_provided_passes(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='Which workshops?',
            type=Question.TYPE_CHOICE_MULTIPLE,
            required=False,
        )
        parent.options.create(answer='Workshop A', identifier='WSA')
        parent.options.create(answer='Workshop B', identifier='WSB')
        child = env['event'].questions.create(
            question='Workshop A: prior experience?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['WSA'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(
        env,
        {
            f'question_{parent.id}': ['WSA'],
            f'question_{child.id}': 'Yes, attended last year',
        },
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multi_checkbox_other_option_skips_followup(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='Which workshops?',
            type=Question.TYPE_CHOICE_MULTIPLE,
            required=False,
        )
        parent.options.create(answer='Workshop A', identifier='WSA')
        parent.options.create(answer='Workshop B', identifier='WSB')
        child = env['event'].questions.create(
            question='Workshop A: prior experience?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['WSA'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {f'question_{parent.id}': ['WSB']})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_multi_checkbox_nothing_selected_skips_followup(env):
    with scopes_disabled():
        parent = env['event'].questions.create(
            question='Which workshops?',
            type=Question.TYPE_CHOICE_MULTIPLE,
            required=False,
        )
        parent.options.create(answer='Workshop A', identifier='WSA')
        child = env['event'].questions.create(
            question='Workshop A: prior experience?',
            type=Question.TYPE_TEXT,
            required=True,
            dependency_question=parent,
            dependency_values=['WSA'],
        )
        env['product'].questions.add(parent, child)
        _add_to_ask(env['product'], parent, child)

    form = _build_form(env, {})
    assert form.is_valid(), form.errors
