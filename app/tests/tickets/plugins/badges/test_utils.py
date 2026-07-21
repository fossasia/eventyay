import datetime
import json

import pytest
from django.core.cache import cache as default_cache
from django.test import override_settings
from django_scopes import scopes_disabled

from eventyay.base.models import (
    CachedTicket,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Question,
    QuestionAnswer,
    Voucher,
)
from eventyay.base.pdf import Renderer, extract_layout_text_placeholders
from eventyay.plugins.badges.exporters import BadgeRenderer, OPTIONS, _renderer, render_badges, render_pdf
from eventyay.plugins.badges.models import BadgeProduct, BadgeVoucher
from eventyay.plugins.badges.utils import (
    BADGE_TICKET_PROVIDER,
    _badge_version_key,
    _renderer_cache,
    clear_badge_layout_cache,
    delete_badge_cached_pdfs,
    get_badge_bundle_option_choices,
    get_badge_customizable_fields,
    get_badge_layout_for_position,
    get_badge_layout_version,
    append_badge_options_additional_field,
    format_badge_option_labels,
    get_badge_options_display,
    position_has_printable_badge,
)


@pytest.fixture
def badge_event():
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
            attendee_name_parts={},
            secret='1234',
        )
        layout = event.badge_layouts.create(
            name='Layout 1',
            default=True,
            allow_customization=True,
            ask_user_fields_data=['attendee_name'],
        )
        yield event, position, product, layout


@pytest.mark.django_db
def test_badge_options_shown_with_default_layout(badge_event):
    """Checkout/modify should offer badge options when only the default layout applies."""
    event, position, product, layout = badge_event

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == 'attendee_name'


@pytest.mark.django_db
def test_badge_options_display_uses_default_layout_on_order_page(badge_event):
    """Order detail should show badge options when only the default layout applies."""
    event, position, product, layout = badge_event

    assert get_badge_bundle_option_choices(event, position)
    display = get_badge_options_display(event, position)
    # Default layout includes attendee_name as an ask-user field.
    assert display
    assert 'name' in display.lower()


@pytest.mark.django_db
def test_badge_options_hidden_without_customization(badge_event):
    event, position, product, layout = badge_event
    layout.allow_customization = False
    layout.ask_user_fields_data = []
    layout.save(update_fields=['allow_customization', 'ask_user_fields'])

    assert get_badge_bundle_option_choices(event, position) == []
    assert get_badge_options_display(event, position) is None


@pytest.mark.django_db
def test_badge_options_display_hidden_when_product_has_no_badge(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=None)

    assert get_badge_options_display(event, position) is None
    assert get_badge_bundle_option_choices(event, position) == []


def test_format_badge_option_labels_empty():
    assert 'No optional badge fields selected' in format_badge_option_labels([])


def test_format_badge_option_labels_joins():
    assert format_badge_option_labels(['Name', 'Company']) == 'Name, Company'


@pytest.mark.django_db
def test_append_badge_options_skips_when_form_field_present(badge_event):
    event, position, product, layout = badge_event
    fields = []
    assert (
        append_badge_options_additional_field(
            event, position, fields, present_keys={'badge_hidden_fields'}
        )
        is False
    )
    assert fields == []


@pytest.mark.django_db
def test_append_badge_options_adds_for_default_layout(badge_event):
    event, position, product, layout = badge_event
    fields = []
    assert append_badge_options_additional_field(event, position, fields) is True
    assert len(fields) == 1
    assert fields[0]['question']
    assert fields[0]['answer']


@pytest.mark.django_db
def test_badge_options_shown_with_product_layout_assignment(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=layout)

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == 'attendee_name'


@pytest.mark.django_db
def test_can_modify_answers_when_only_badge_options_exist(badge_event):
    event, position, product, layout = badge_event
    event.settings.set('invoice_address_asked', False)
    event.settings.set('attendee_names_asked', False)
    event.settings.set('attendee_emails_asked', False)
    event.settings.set('allow_modifications', 'order')

    assert not product.questions.exists()
    assert position.order.can_modify_answers


@pytest.mark.django_db
def test_can_modify_answers_false_when_badge_customization_disabled(badge_event):
    event, position, product, layout = badge_event
    layout.allow_customization = False
    layout.ask_user_fields_data = []
    layout.save(update_fields=['allow_customization', 'ask_user_fields'])
    event.settings.set('invoice_address_asked', False)
    event.settings.set('attendee_names_asked', False)
    event.settings.set('attendee_emails_asked', False)
    event.settings.set('allow_modifications', 'order')

    assert not position.order.can_modify_answers


@pytest.mark.django_db
def test_badge_options_hidden_when_product_explicitly_has_no_layout(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=None)

    assert get_badge_bundle_option_choices(event, position) == []


@pytest.mark.django_db
def test_voucher_explicit_assignment_enables_checkout_options(badge_event):
    event, position, product, layout = badge_event
    voucher = Voucher.objects.create(event=event, code='VOUCHER3')
    position.voucher = voucher
    position.save(update_fields=['voucher'])
    BadgeVoucher.objects.create(voucher=voucher, layout=layout)

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == 'attendee_name'


@pytest.mark.django_db
def test_voucher_layout_overrides_product_default(badge_event):
    event, position, product, layout = badge_event
    voucher_layout = event.badge_layouts.create(name='Voucher layout')
    voucher = Voucher.objects.create(event=event, code='VOUCHER1')
    position.voucher = voucher
    position.save(update_fields=['voucher'])

    BadgeVoucher.objects.create(voucher=voucher, layout=voucher_layout)

    assert get_badge_layout_for_position(event, position) == voucher_layout
    assert position_has_printable_badge(event, position) is True


@pytest.mark.django_db
def test_voucher_layout_none_disables_badge_even_with_default_product(badge_event):
    event, position, product, layout = badge_event
    voucher = Voucher.objects.create(event=event, code='VOUCHER2')
    position.voucher = voucher
    position.save(update_fields=['voucher'])

    BadgeVoucher.objects.create(voucher=voucher, layout=None)

    assert get_badge_layout_for_position(event, position) is None
    assert position_has_printable_badge(event, position) is False


def test_fit_fontsize_to_width_shrinks_unbreakable_text():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'VeryLongAttendeeNameExample',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted < 12.0
    assert fitted >= 4.0


def test_fit_fontsize_to_width_keeps_wrappable_text_at_max():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'Very Long Attendee Name Example',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0


def test_fit_fontsize_to_width_keeps_short_text_at_max():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'Ann',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0


def test_fit_fontsize_to_width_multiline_uses_longest_line():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'John\nDoe',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0


def test_extract_layout_text_placeholders():
    assert extract_layout_text_placeholders('{question_1} {question_2}') == ['question_1', 'question_2']
    assert extract_layout_text_placeholders('Plain text') == []


@pytest.mark.django_db
def test_renderer_other_text_resolves_question_placeholders(badge_event):
    event, position, product, layout = badge_event
    q1 = Question.objects.create(event=event, question='First name', type='S')
    q2 = Question.objects.create(event=event, question='Last name', type='S')
    QuestionAnswer.objects.create(orderposition=position, question=q1, answer='Jane')
    QuestionAnswer.objects.create(orderposition=position, question=q2, answer='Doe')

    renderer = BadgeRenderer(event, [], None)
    result = renderer._get_text_content(
        position,
        position.order,
        {'content': 'other', 'text': '{question:First name} {question:Last name}'},
    )

    assert result == 'Jane Doe'


@pytest.mark.django_db
def test_badge_renderer_other_text_hides_placeholder_fields(badge_event):
    event, position, product, layout = badge_event
    q1 = Question.objects.create(event=event, question='First name', type='S')
    q2 = Question.objects.create(event=event, question='Last name', type='S')
    QuestionAnswer.objects.create(orderposition=position, question=q1, answer='Jane')
    QuestionAnswer.objects.create(orderposition=position, question=q2, answer='Doe')
    position.meta_info_data = {'question_form_data': {'badge_hidden_fields': [f'question_{q1.pk}']}}
    position.save(update_fields=['meta_info'])

    renderer = BadgeRenderer(
        event,
        [],
        None,
        ask_user_fields=[f'question_{q1.pk}', f'question_{q2.pk}'],
    )
    result = renderer._get_text_content(
        position,
        position.order,
        {'content': 'other', 'text': '{question:First name} {question:Last name}'},
    )

    assert result == ' Doe'


@pytest.mark.django_db
def test_customizable_fields_include_questions_mixed_in_other_text(badge_event):
    """Questions embedded in free-text "other" blocks must appear as Ask-user options."""
    event, position, product, layout = badge_event
    q1 = Question.objects.create(event=event, question='First name', type='S')
    q2 = Question.objects.create(event=event, question='Last name', type='S')
    layout.layout = json.dumps(
        [
            {
                'type': 'textarea',
                'left': '0',
                'bottom': '80',
                'fontsize': '12.0',
                'content': 'other',
                'text': '{question:First name} {question:Last name} / {attendee_company}',
            }
        ]
    )
    layout.allow_customization = True
    layout.ask_user_fields_data = [f'question_{q1.pk}', f'question_{q2.pk}', 'attendee_company']
    layout.save(update_fields=['layout', 'allow_customization', 'ask_user_fields'])
    clear_badge_layout_cache(event)

    keys = [field['key'] for field in get_badge_customizable_fields(event, layout)]
    assert keys == [f'question_{q1.pk}', f'question_{q2.pk}', 'attendee_company']

    choices = get_badge_bundle_option_choices(event, position)
    assert [key for key, _label in choices] == [f'question_{q1.pk}', f'question_{q2.pk}', 'attendee_company']
    assert dict(choices)[f'question_{q1.pk}'] == 'First name'


@pytest.mark.django_db
def test_customizable_fields_include_question_id_placeholders_in_other_text(badge_event):
    event, position, product, layout = badge_event
    q1 = Question.objects.create(event=event, question='Handle', type='S')
    layout.layout = json.dumps(
        [
            {
                'type': 'textarea',
                'content': 'other',
                'text': f'Hello {{question_{q1.pk}}}',
            }
        ]
    )
    layout.allow_customization = True
    layout.ask_user_fields_data = [f'question_{q1.pk}']
    layout.save(update_fields=['layout', 'allow_customization', 'ask_user_fields'])
    clear_badge_layout_cache(event)

    keys = [field['key'] for field in get_badge_customizable_fields(event, layout)]
    assert keys == [f'question_{q1.pk}']
    assert get_badge_bundle_option_choices(event, position) == [(f'question_{q1.pk}', 'Handle')]


@pytest.mark.django_db
def test_renderer_other_text_still_supports_question_id_placeholders(badge_event):
    event, position, product, layout = badge_event
    q1 = Question.objects.create(event=event, question='First name', type='S')
    QuestionAnswer.objects.create(orderposition=position, question=q1, answer='Jane')

    renderer = BadgeRenderer(event, [], None)
    result = renderer._get_text_content(
        position,
        position.order,
        {'content': 'other', 'text': f'{{question_{q1.pk}}}'},
    )

    assert result == 'Jane'


def _textarea_field(content, *, bottom='85', bold=False, text=None):
    return {
        'type': 'textarea',
        'left': '0',
        'bottom': bottom,
        'fontsize': '12.0',
        'color': [0, 0, 0, 1],
        'fontfamily': 'Open Sans',
        'bold': bold,
        'italic': False,
        'width': '80',
        'content': content,
        'text': text or content,
        'align': 'center',
    }


def _set_default_layout(event, layout):
    event.badge_layouts.exclude(pk=layout.pk).update(default=False)
    layout.default = True
    layout.save(update_fields=['default'])


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'badge-layout-version-tests',
        }
    }
)
def test_badge_layout_version_survives_event_cache_clear(badge_event):
    event, position, product, layout = badge_event

    # Store the version outside NamespacedCache so event.cache.clear() cannot
    # rotate it away (the production bug that left workers on version 0).
    default_cache.set(_badge_version_key(event), 42, 3600)
    assert get_badge_layout_version(event) == 42

    event.cache.clear()
    assert get_badge_layout_version(event) == 42
    assert default_cache.get(_badge_version_key(event)) == 42

    clear_badge_layout_cache(event)
    assert get_badge_layout_version(event) == 43


@pytest.mark.django_db
def test_default_layout_switch_is_reflected_immediately(badge_event):
    event, position, product, layout = badge_event
    other = event.badge_layouts.create(name='Layout 2', default=False)

    assert get_badge_layout_for_position(event, position).pk == layout.pk

    _set_default_layout(event, other)
    clear_badge_layout_cache(event)

    assert get_badge_layout_for_position(event, position).pk == other.pk


@pytest.mark.django_db
def test_render_badges_uses_latest_default_even_without_prior_cache_clear(badge_event):
    event, position, product, layout = badge_event
    other = event.badge_layouts.create(
        name='Layout 2',
        default=False,
        layout=json.dumps([_textarea_field('attendee_company', text='Company')]),
    )

    # Prime an in-process assignment snapshot pointing at the old default.
    assert get_badge_layout_for_position(event, position).pk == layout.pk

    _set_default_layout(event, other)
    # Intentionally skip clear_badge_layout_cache: render must still see DB truth.

    Renderer._register_fonts()
    _renderer_cache.clear()
    badge_pdf, num_pages = render_badges(event, [position], OPTIONS['one'])
    assert num_pages == 1
    assert len(badge_pdf.pages) == 1

    selected = get_badge_layout_for_position(event, position)
    assert selected.pk == other.pk
    renderer = _renderer(event, selected, get_badge_layout_version(event))
    assert [field['content'] for field in renderer.layout] == ['attendee_company']


@pytest.mark.django_db
def test_product_assignment_overrides_default_layout(badge_event):
    event, position, product, layout = badge_event
    assigned = event.badge_layouts.create(name='Assigned', default=False)
    BadgeProduct.objects.create(product=product, layout=assigned)
    clear_badge_layout_cache(event)

    assert get_badge_layout_for_position(event, position).pk == assigned.pk


@pytest.mark.django_db
def test_renderer_cache_uses_updated_layout_content(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=layout)

    _renderer_cache.clear()
    version = get_badge_layout_version(event)
    renderer1 = _renderer(event, layout, version)
    initial_count = len(renderer1.layout)

    layout.layout = json.dumps(
        renderer1.layout + [_textarea_field('attendee_company', bottom='70', text='Sample company')]
    )
    layout.save(update_fields=['layout'])
    clear_badge_layout_cache(event)

    layout.refresh_from_db()
    renderer2 = _renderer(event, layout, get_badge_layout_version(event))
    assert renderer2 is not renderer1
    assert len(renderer2.layout) == initial_count + 1


@pytest.mark.django_db
def test_render_badges_uses_selected_default_layout_fields(badge_event):
    event, position, product, layout = badge_event
    layout.layout = json.dumps(
        [
            _textarea_field('attendee_name', bold=True, text='John Doe'),
            _textarea_field('attendee_company', bottom='70', text='Company'),
        ]
    )
    layout.save(update_fields=['layout'])
    clear_badge_layout_cache(event)
    _renderer_cache.clear()

    selected = get_badge_layout_for_position(event, position)
    assert selected.pk == layout.pk
    assert len(selected.layout_data) == 2

    Renderer._register_fonts()
    renderer = _renderer(event, selected, get_badge_layout_version(event))
    assert renderer is not None
    assert len(renderer.layout) == 2
    assert {field['content'] for field in renderer.layout} == {'attendee_name', 'attendee_company'}


@pytest.mark.django_db
def test_end_to_end_layout_selection_content_and_pdf_cache(badge_event):
    """Full path: voucher wins, content edits apply, PDF cache clears, export renders."""
    event, position, product, default_layout = badge_event
    product_layout = event.badge_layouts.create(
        name='Product layout',
        default=False,
        layout=json.dumps([_textarea_field('attendee_name', text='Name')]),
    )
    voucher_layout = event.badge_layouts.create(
        name='Voucher layout',
        default=False,
        layout=json.dumps(
            [
                _textarea_field('attendee_name', text='Name'),
                _textarea_field('attendee_company', bottom='70', text='Company'),
            ]
        ),
    )
    BadgeProduct.objects.create(product=product, layout=product_layout)
    voucher = Voucher.objects.create(event=event, code='ENDTOEND')
    position.voucher = voucher
    position.save(update_fields=['voucher'])
    BadgeVoucher.objects.create(voucher=voucher, layout=voucher_layout)

    # Stale assignment snapshot must not win over DB truth on render.
    assert get_badge_layout_for_position(event, position).pk == voucher_layout.pk

    voucher_layout.layout = json.dumps(
        [
            _textarea_field('attendee_name', text='Name'),
            _textarea_field('attendee_company', bottom='70', text='Company'),
            _textarea_field('attendee_job_title', bottom='55', text='Job'),
        ]
    )
    voucher_layout.save(update_fields=['layout'])
    # No clear_badge_layout_cache: render_badges must still use updated fields.

    CachedTicket.objects.create(
        order_position=position,
        provider=BADGE_TICKET_PROVIDER,
        type='application/pdf',
        extension='.pdf',
    )
    assert CachedTicket.objects.filter(order_position=position, provider=BADGE_TICKET_PROVIDER).exists()
    delete_badge_cached_pdfs(event)
    assert not CachedTicket.objects.filter(order_position=position, provider=BADGE_TICKET_PROVIDER).exists()

    Renderer._register_fonts()
    _renderer_cache.clear()
    pdf = render_pdf(event, [position], OPTIONS['one'])
    assert pdf.read(5) == b'%PDF-'

    selected = get_badge_layout_for_position(event, position)
    assert selected.pk == voucher_layout.pk
    renderer = _renderer(event, selected, get_badge_layout_version(event))
    assert {field['content'] for field in renderer.layout} == {
        'attendee_name',
        'attendee_company',
        'attendee_job_title',
    }
    assert get_badge_layout_for_position(event, position).pk != default_layout.pk
    assert get_badge_layout_for_position(event, position).pk != product_layout.pk


def test_badge_provider_skips_persisted_ticket_cache():
    """Single-order/control downloads must not reuse stale CachedTicket rows."""
    from eventyay.base.services.tickets import _PROVIDERS_WITHOUT_TICKET_CACHE

    assert BADGE_TICKET_PROVIDER in _PROVIDERS_WITHOUT_TICKET_CACHE
