import pytest
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Product
from eventyay.base.services.export import ExportError
from eventyay.plugins.reports.exporters import OverviewReport


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())


@pytest.mark.django_db
def test_order_overview_pdf_without_products_reports_no_data(event):
    """Used to fail with IndexError: tuple index out of range while building the Total row."""
    with pytest.raises(ExportError, match='No data to export'):
        OverviewReport(event).render({})


@pytest.mark.django_db
def test_order_overview_pdf_renders_with_products(event):
    Product.objects.create(event=event, name='Ticket', default_price=23)

    filename, content_type, content = OverviewReport(event).render({})

    assert filename == 'report-dummy.pdf'
    assert content_type == 'application/pdf'
    assert content.startswith(b'%PDF')
