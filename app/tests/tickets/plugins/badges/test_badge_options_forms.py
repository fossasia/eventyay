"""End-to-end coverage for badge options on checkout and modify-answers forms."""

import datetime

import pytest
from django.http import QueryDict
from django_scopes import scopes_disabled

from eventyay.base.forms.questions import BaseQuestionsForm
from eventyay.base.models import (
    CartPosition,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
)
from eventyay.base.views.mixins import BaseQuestionsViewMixin
from eventyay.plugins.badges.models import BadgeProduct
from eventyay.plugins.badges.signals import badge_question_form_fields
from eventyay.plugins.badges.utils import (
    BADGE_HIDDEN_FIELDS_KEY,
    get_badge_bundle_option_choices,
    get_badge_hidden_fields,
)


@pytest.fixture
def badge_checkout_env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Badge Org', slug='badge-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Badge Event',
            slug='badge-event',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2030, 12, 26, tzinfo=datetime.timezone.utc),
        )
        event.settings.set('invoice_address_asked', False)
        event.settings.set('attendee_names_asked', False)
        event.settings.set('attendee_emails_asked', False)
        event.settings.set('allow_modifications', 'order')

        product = Product.objects.create(event=event, name='Standard', default_price=0, admission=True)
        product.questions_to_ask = []

        layout = event.badge_layouts.create(
            name='Default',
            default=True,
            allow_customization=True,
            ask_user_fields_data=['attendee_name', 'attendee_company'],
        )

        cart = CartPosition.objects.create(
            event=event,
            cart_id='badge-cart',
            product=product,
            price=0,
            expires=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30),
        )

        order = Order.objects.create(
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
            expires=datetime.datetime(2030, 2, 1, tzinfo=datetime.timezone.utc),
            total=0,
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=0,
            secret='badge-secret',
        )

        yield {
            'event': event,
            'product': product,
            'layout': layout,
            'cart': cart,
            'order': order,
            'position': position,
        }


def _split_badge_fields(form):
    """Mirror BaseQuestionsViewMixin form field splitting used by templates."""
    form.badge_option_fields = []
    form.regular_fields = []
    for field_name in form.fields:
        bound = form[field_name]
        if getattr(bound.field, 'badge_option', False):
            form.badge_option_fields.append(bound)
        else:
            form.regular_fields.append(bound)
    return form


def _prefixed_form_data(prefix, data):
    query = QueryDict(mutable=True)
    for key, value in data.items():
        field_name = f'{prefix}-{key}'
        if isinstance(value, (list, tuple)):
            for item in value:
                query.appendlist(field_name, item)
        else:
            query[field_name] = value
    return query


def _build_cart_form(env, data=None):
    prefix = str(env['cart'].pk)
    kwargs = {
        'event': env['event'],
        'cartpos': env['cart'],
        'all_optional': False,
        'prefix': prefix,
    }
    if data is not None:
        kwargs['data'] = _prefixed_form_data(prefix, data)
    return BaseQuestionsForm(**kwargs)


def _build_order_form(env, data=None):
    prefix = str(env['position'].pk)
    kwargs = {
        'event': env['event'],
        'orderpos': env['position'],
        'all_optional': False,
        'prefix': prefix,
    }
    if data is not None:
        kwargs['data'] = _prefixed_form_data(prefix, data)
    return BaseQuestionsForm(**kwargs)


@pytest.mark.django_db
def test_signal_injects_badge_options_for_default_layout(badge_checkout_env):
    env = badge_checkout_env
    fields = badge_question_form_fields(env['event'], env['cart'])
    assert BADGE_HIDDEN_FIELDS_KEY in fields
    assert [c[0] for c in fields[BADGE_HIDDEN_FIELDS_KEY].choices] == [
        'attendee_name',
        'attendee_company',
    ]


@pytest.mark.django_db
def test_checkout_form_shows_badge_options_with_default_layout(badge_checkout_env):
    env = badge_checkout_env
    form = _split_badge_fields(_build_cart_form(env))

    assert BADGE_HIDDEN_FIELDS_KEY in form.fields
    assert len(form.badge_option_fields) == 1
    assert form.badge_option_fields[0].name == BADGE_HIDDEN_FIELDS_KEY
    assert set(form.fields[BADGE_HIDDEN_FIELDS_KEY].initial) == {
        'attendee_name',
        'attendee_company',
    }


@pytest.mark.django_db
def test_modify_answers_form_shows_badge_options_with_default_layout(badge_checkout_env):
    env = badge_checkout_env
    form = _split_badge_fields(_build_order_form(env))

    assert BADGE_HIDDEN_FIELDS_KEY in form.fields
    assert len(form.badge_option_fields) == 1
    assert form.orderpos == env['position']


@pytest.mark.django_db
def test_checkout_and_modify_save_hidden_fields_semantics(badge_checkout_env):
    """Checked boxes = visible; cleaned value stores unchecked (hidden) keys."""
    env = badge_checkout_env

    cart_form = _build_cart_form(env, {BADGE_HIDDEN_FIELDS_KEY: ['attendee_name']})
    assert cart_form.is_valid()
    assert cart_form.cleaned_data[BADGE_HIDDEN_FIELDS_KEY] == ['attendee_company']

    order_form = _build_order_form(env, {BADGE_HIDDEN_FIELDS_KEY: ['attendee_company']})
    assert order_form.is_valid()
    assert order_form.cleaned_data[BADGE_HIDDEN_FIELDS_KEY] == ['attendee_name']


@pytest.mark.django_db
def test_mixin_save_persists_badge_options_on_order_and_cart(badge_checkout_env):
    env = badge_checkout_env

    class _Saver(BaseQuestionsViewMixin):
        def __init__(self, forms):
            self._forms = forms

        @property
        def forms(self):
            return self._forms

        def get_question_override_sets(self, *args, **kwargs):
            return []

    cart_form = _build_cart_form(env, {BADGE_HIDDEN_FIELDS_KEY: ['attendee_name']})
    cart_form.pos = env['cart']
    order_form = _build_order_form(env, {BADGE_HIDDEN_FIELDS_KEY: ['attendee_name']})
    order_form.pos = env['position']

    assert _Saver([cart_form, order_form]).save() is True

    env['cart'].refresh_from_db()
    env['position'].refresh_from_db()
    assert get_badge_hidden_fields(env['cart']) == ['attendee_company']
    assert get_badge_hidden_fields(env['position']) == ['attendee_company']


@pytest.mark.django_db
def test_forms_hidden_when_product_has_explicit_no_badge(badge_checkout_env):
    from eventyay.plugins.badges.utils import clear_badge_layout_cache

    env = badge_checkout_env
    BadgeProduct.objects.create(product=env['product'], layout=None)
    clear_badge_layout_cache(env['event'])

    assert get_badge_bundle_option_choices(env['event'], env['cart']) == []
    assert badge_question_form_fields(env['event'], env['cart']) == {}
    assert BADGE_HIDDEN_FIELDS_KEY not in _build_cart_form(env).fields
    assert BADGE_HIDDEN_FIELDS_KEY not in _build_order_form(env).fields
    assert not env['order'].can_modify_answers


@pytest.mark.django_db
def test_forms_shown_with_explicit_product_assignment(badge_checkout_env):
    from eventyay.plugins.badges.utils import clear_badge_layout_cache

    env = badge_checkout_env
    BadgeProduct.objects.create(product=env['product'], layout=env['layout'])
    clear_badge_layout_cache(env['event'])

    assert BADGE_HIDDEN_FIELDS_KEY in _build_cart_form(env).fields
    assert BADGE_HIDDEN_FIELDS_KEY in _build_order_form(env).fields
    assert env['order'].can_modify_answers


@pytest.mark.django_db
def test_addon_position_does_not_get_own_badge_options(badge_checkout_env):
    env = badge_checkout_env
    with scopes_disabled():
        addon_product = Product.objects.create(event=env['event'], name='Addon', default_price=0)
        addon_product.questions_to_ask = []
        addon = OrderPosition.objects.create(
            order=env['order'],
            product=addon_product,
            price=0,
            secret='addon-secret',
            addon_to=env['position'],
        )

    assert badge_question_form_fields(env['event'], addon) == {}
    assert BADGE_HIDDEN_FIELDS_KEY in badge_question_form_fields(env['event'], env['position'])


@pytest.mark.django_db
def test_modify_answers_initial_reflects_saved_hidden_fields(badge_checkout_env):
    env = badge_checkout_env
    env['position'].meta_info_data = {
        'question_form_data': {BADGE_HIDDEN_FIELDS_KEY: ['attendee_company']}
    }
    env['position'].save(update_fields=['meta_info'])

    form = _build_order_form(env)
    assert set(form.fields[BADGE_HIDDEN_FIELDS_KEY].initial) == {'attendee_name'}


@pytest.mark.django_db
def test_can_modify_answers_requires_active_ask_user_fields(badge_checkout_env):
    from eventyay.plugins.badges.utils import clear_badge_layout_cache

    env = badge_checkout_env
    assert env['order'].can_modify_answers

    env['layout'].ask_user_fields_data = []
    env['layout'].save(update_fields=['ask_user_fields'])
    clear_badge_layout_cache(env['event'])
    assert not env['order'].can_modify_answers
