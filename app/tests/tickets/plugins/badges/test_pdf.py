from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.utils.timezone import now
from django_scopes import scope
from pypdf import PdfReader, PdfWriter

from eventyay.base.models import (
    Event,
    Product as Item,
    ProductVariation as ItemVariation,
    Order,
    OrderPosition,
    Organizer,
)
from eventyay.base.services.orders import OrderError
from eventyay.plugins.badges.exporters import BadgeExporter, OPTIONS, render_nup


def _render_form(shirt, **kwargs):
    defaults = {'products': [shirt.pk], 'include_pending': True}
    defaults.update(kwargs)
    return defaults


@pytest.fixture
def env():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    with scope(organizer=o):
        event = Event.objects.create(organizer=o, name='Dummy', slug='dummy', date_from=now(), live=True)
        o1 = Order.objects.create(
            code='FOOBAR',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('13.37'),
        )
        shirt = Item.objects.create(event=event, name='T-Shirt', default_price=12)
        shirt_red = ItemVariation.objects.create(item=shirt, default_price=14, value='Red')
        OrderPosition.objects.create(
            order=o1,
            item=shirt,
            variation=shirt_red,
            price=12,
            attendee_name_parts={},
            secret='1234',
        )
        OrderPosition.objects.create(
            order=o1,
            item=shirt,
            variation=shirt_red,
            price=12,
            attendee_name_parts={},
            secret='5678',
        )
        yield event, o1, shirt


@pytest.mark.django_db
def test_generate_pdf(env):
    event, order, shirt = env
    event.badge_layouts.create(name='Default', default=True)
    e = BadgeExporter(event)
    with pytest.raises(OrderError):
        e.render(_render_form(shirt, include_pending=False, rendering='one'))

    with pytest.raises(OrderError):
        e.render({'products': [], 'rendering': 'one', 'include_pending': True})

    fname, ftype, buf = e.render(_render_form(shirt, rendering='one'))
    assert ftype == 'application/pdf'
    pdf = PdfReader(BytesIO(buf))
    assert len(pdf.pages) == 2


@pytest.mark.django_db
def test_generate_pdf_multi(env):
    event, order, shirt = env
    event.badge_layouts.create(name='Default', default=True)
    e = BadgeExporter(event)
    fname, ftype, buf = e.render(_render_form(shirt, rendering='a4_a6l'))
    assert ftype == 'application/pdf'
    pdf = PdfReader(BytesIO(buf))
    assert len(pdf.pages) == 1
    expected_size = OPTIONS['a4_a6l']['pagesize']
    page = pdf.pages[0].mediabox
    assert float(page.width) == pytest.approx(float(expected_size[0]), rel=0.01)
    assert float(page.height) == pytest.approx(float(expected_size[1]), rel=0.01)


def test_render_nup_large_export_merge(tmp_path):
    badges_per_page = OPTIONS['a4_a6l']['cols'] * OPTIONS['a4_a6l']['rows']
    num_badges = badges_per_page * 20 + 1

    badge_pdf_path = tmp_path / 'badges.pdf'
    writer = PdfWriter()
    for _ in range(num_badges):
        writer.add_blank_page(width=200, height=200)
    with badge_pdf_path.open('wb') as handle:
        writer.write(handle)

    outbuffer = BytesIO()
    render_nup([str(badge_pdf_path)], num_badges, outbuffer, OPTIONS['a4_a6l'])

    pdf = PdfReader(outbuffer)
    assert len(pdf.pages) == (num_badges + badges_per_page - 1) // badges_per_page
