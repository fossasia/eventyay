import datetime

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Product, Voucher
from eventyay.plugins.badges.exporters import SEARCHABLE_SCROLLING_CHECKBOXES, BadgeExporter, searchable_scrolling_checkbox_widget


@pytest.fixture
def badge_export_event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc')
        event = Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        Product.objects.create(event=event, name='Standard', default_price=0, position=1, admission=True)
        Voucher.objects.create(event=event, code='scholar_ABC123')
        yield event


@pytest.mark.django_db
def test_badge_export_products_and_vouchers_use_searchable_widget(badge_export_event):
    exporter = BadgeExporter(badge_export_event)
    fields = exporter.export_form_fields
    expected_widget = searchable_scrolling_checkbox_widget()

    for field_name in ('products', 'vouchers'):
        widget = fields[field_name].widget
        assert widget.__class__ is expected_widget.__class__
        assert widget.attrs.get('class') == expected_widget.attrs.get('class')
        assert SEARCHABLE_SCROLLING_CHECKBOXES in widget.attrs.get('class', '')