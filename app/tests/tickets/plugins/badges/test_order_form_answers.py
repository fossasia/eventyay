import datetime
import json

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, Question, QuestionAnswer
from eventyay.base.pdf import get_variables, remap_question_content_key
from eventyay.plugins.badges.exporters import BadgeRenderer
from eventyay.plugins.badges.models import BadgeProduct
from eventyay.plugins.badges.utils import (
    get_badge_bundle_option_choices,
    get_badge_customizable_fields,
    get_badge_visible_field_values,
)


@pytest.fixture
def badge_question_event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc')
        event = Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        product = Product.objects.create(event=event, name='Standard', default_price=0, position=1)
        question = Question.objects.create(
            event=event,
            question='T-Shirt size',
            type=Question.TYPE_STRING,
            identifier='tshirt_size',
        )
        question.products.add(product)
        order = Order.objects.create(
            event=event,
            email='dummy@dummy.test',
            status='p',
            datetime=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            expires=datetime.datetime(2014, 1, 26, tzinfo=datetime.timezone.utc),
            total=0,
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=0,
            attendee_name_parts={'_scheme': 'full', 'full_name': 'Jane Doe'},
            secret='1234',
        )
        QuestionAnswer.objects.create(
            orderposition=position,
            question=question,
            answer='XL',
        )
        layout = event.badge_layouts.create(
            name='Layout 1',
            default=True,
            allow_customization=True,
            ask_user_fields_data=[f'question_{question.identifier}'],
            layout=json.dumps(
                [
                    {
                        'type': 'textarea',
                        'left': '0',
                        'bottom': '85',
                        'fontsize': '12.0',
                        'color': [0, 0, 0, 1],
                        'fontfamily': 'Open Sans',
                        'bold': False,
                        'italic': False,
                        'width': '80',
                        'content': f'question_{question.identifier}',
                        'text': 'XL',
                        'align': 'center',
                    }
                ]
            ),
        )
        BadgeProduct.objects.create(product=product, layout=layout)
        yield event, position, product, question, layout


@pytest.mark.django_db
def test_get_variables_exposes_question_by_identifier(badge_question_event):
    event, _position, _product, question, _layout = badge_question_event

    variables = get_variables(event)

    assert f'question_{question.pk}' in variables
    assert f'question_{question.identifier}' in variables
    assert variables[f'question_{question.identifier}']['label']


@pytest.mark.django_db
def test_badge_customizable_fields_include_question_identifier(badge_question_event):
    event, _position, _product, question, layout = badge_question_event

    fields = get_badge_customizable_fields(event, layout)

    assert any(field['key'] == f'question_{question.identifier}' for field in fields)


@pytest.mark.django_db
def test_badge_renderer_uses_order_form_answer_by_primary_key(badge_question_event):
    event, position, _product, question, layout = badge_question_event

    renderer = BadgeRenderer(event, layout.layout_data, None)
    content = renderer._get_text_content(
        position,
        position.order,
        {'content': f'question_{question.pk}'},
    )

    assert content == 'XL'


@pytest.mark.django_db
def test_badge_renderer_uses_order_form_answer(badge_question_event):
    event, position, _product, question, layout = badge_question_event

    renderer = BadgeRenderer(event, layout.layout_data, None)
    content = renderer._get_text_content(
        position,
        position.order,
        {'content': f'question_{question.identifier}'},
    )

    assert content == 'XL'


@pytest.mark.django_db
def test_badge_options_use_question_sample_label(badge_question_event):
    event, position, _product, question, _layout = badge_question_event

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == f'question_{question.identifier}'
    assert choices[0][1] == str(question.question)


@pytest.mark.django_db
def test_badge_visible_field_values_include_question_answer(badge_question_event):
    event, position, _product, _question, _layout = badge_question_event

    values = get_badge_visible_field_values(event, position)

    assert values == ['XL']


@pytest.mark.django_db
def test_badge_renderer_hides_opt_out_question_field(badge_question_event):
    event, position, _product, question, layout = badge_question_event
    position.meta_info_data = {
        'question_form_data': {
            'badge_hidden_fields': [f'question_{question.identifier}'],
        }
    }

    renderer = BadgeRenderer(
        event,
        layout.layout_data,
        None,
        ask_user_fields=layout.ask_user_fields_data,
    )
    content = renderer._get_text_content(
        position,
        position.order,
        {'content': f'question_{question.identifier}'},
    )

    assert content == ''


@pytest.mark.django_db
def test_remap_question_content_key_supports_identifier():
    class DummyQuestion:
        def __init__(self, pk):
            self.pk = pk

    question_map = {7: DummyQuestion(42)}
    identifier_map = {'tshirt_size': DummyQuestion(42)}

    assert remap_question_content_key('question_7', question_map, identifier_map) == 'question_42'
    assert remap_question_content_key('question_tshirt_size', question_map, identifier_map) == 'question_42'
    assert remap_question_content_key('question_99', {99: DummyQuestion(55)}, {'99': DummyQuestion(55)}) == 'question_55'
    assert remap_question_content_key('attendee_name', question_map, identifier_map) == 'attendee_name'
    assert remap_question_content_key('question_missing', question_map, identifier_map) == 'question_missing'
