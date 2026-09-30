import pytest
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer
from eventyay.plugins.reports.exporters import OverviewReport


@pytest.mark.django_db
def test_order_overview_pdf_renders_without_products():
    """Used to fail with IndexError: tuple index out of range while building the Total row."""
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())

    filename, content_type, content = OverviewReport(event).render({})

    assert filename == 'report-dummy.pdf'
    assert content_type == 'application/pdf'
    assert content.startswith(b'%PDF')
