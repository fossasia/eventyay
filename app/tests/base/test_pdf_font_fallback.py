import datetime
from io import BytesIO

import pytest
from django_scopes import scopes_disabled
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.base.pdf import Renderer, font_supports_text, resolve_textarea_font


@pytest.fixture(autouse=True)
def registered_fonts():
    Renderer._register_fonts()


@pytest.fixture
def position():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy',
            slug='dummy',
            date_from=datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC),
        )
        product = Product.objects.create(event=event, name='Ticket', default_price=0)
        order = Order.objects.create(
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC),
            expires=datetime.datetime(2026, 10, 10, tzinfo=datetime.UTC),
            total=0,
        )
        yield OrderPosition.objects.create(order=order, product=product, price=0, attendee_name_parts={}, secret='1234')


@pytest.mark.parametrize(
    'font,expected',
    [
        ('Droid Sans Fallback', 'Open Sans'),
        ('Droid Sans Fallback B', 'Open Sans B'),
        ('Droid Sans Fallback I', 'Open Sans I'),
        ('Droid Sans Fallback B I', 'Open Sans B I'),
        ('Open Sans', 'Open Sans'),
        ('Open Sans B', 'Open Sans B'),
    ],
)
def test_latin_text_falls_back_to_open_sans(font, expected):
    assert resolve_textarea_font(font, 'Jane Member') == (expected, 'Jane Member')


def test_cjk_text_keeps_font_with_cjk_glyphs():
    assert resolve_textarea_font('Droid Sans Fallback', '王小明') == ('Droid Sans Fallback', '王小明')


def test_mixed_text_base_font_draws_latin():
    font, text = resolve_textarea_font('Droid Sans Fallback', 'Jane 王小明')
    assert text == 'Jane 王小明'
    assert font_supports_text(font, 'Jane ')


@pytest.mark.django_db
@pytest.mark.parametrize('bold', [False, True])
def test_rendered_pdf_contains_latin_text_in_font_without_latin_glyphs(position, bold):
    layout = [
        {
            'type': 'textarea',
            'left': '10.00',
            'bottom': '200.00',
            'fontsize': '16.0',
            'color': [0, 0, 0, 1],
            'fontfamily': 'Droid Sans Fallback',
            'bold': bold,
            'italic': False,
            'width': '150.00',
            'content': 'other',
            'text': 'Hello World',
            'align': 'left',
        }
    ]
    with scopes_disabled():
        buffer = BytesIO()
        canvas = Canvas(buffer, pagesize=A4)
        Renderer(position.order.event, layout, None).draw_page(canvas, position.order, position)
        canvas.save()

    assert 'Hello World' in PdfReader(BytesIO(buffer.getvalue())).pages[0].extract_text()
