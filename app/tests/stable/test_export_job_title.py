from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone, translation
from django_scopes import scope

from eventyay.base.exporters.orderlist import OrderListExporter
from eventyay.base.models import InvoiceAddress, Order, OrderPosition, Product
from eventyay.plugins.checkinlists.exporters import CSVCheckinList, PDFCheckinList


def create_paid_order(event, code: str) -> Order:
    now = timezone.now()
    return Order.objects.create(
        event=event,
        code=code,
        email=f'{code.lower()}@example.org',
        status=Order.STATUS_PAID,
        datetime=now,
        expires=now + timedelta(days=7),
        total=Decimal('25.00'),
        locale='en',
    )


@pytest.mark.django_db
def test_order_list_export_orders_includes_job_title(event):
    with scope(organizer=event.organizer, event=event), translation.override('en'):
        ticket = Product.objects.create(
            event=event, name='Conference Pass', default_price=Decimal('25.00'), admission=True
        )
        workshop = Product.objects.create(event=event, name='Workshop', default_price=Decimal('0.00'), admission=False)

        order_direct = create_paid_order(event, 'ORD01')
        OrderPosition.objects.create(
            order=order_direct,
            positionid=1,
            product=ticket,
            price=Decimal('25.00'),
            attendee_name_parts={'full_name': 'Ada Lovelace', '_scheme': 'full'},
            company='Analytical Engines Ltd',
            job_title='Staff Engineer',
        )

        order_addon = create_paid_order(event, 'ORD02')
        base_position = OrderPosition.objects.create(
            order=order_addon,
            positionid=1,
            product=ticket,
            price=Decimal('25.00'),
            canceled=True,
            attendee_name_parts={'full_name': 'Grace Hopper', '_scheme': 'full'},
            job_title='Principal Architect',
        )
        OrderPosition.objects.create(
            order=order_addon,
            positionid=2,
            product=workshop,
            addon_to=base_position,
            price=Decimal('0.00'),
        )

        exporter = OrderListExporter(event)
        rows = [
            row
            for row in exporter.iterate_orders({'paid_only': True})
            if not isinstance(row, exporter.ProgressSetTotal)
        ]

    headers = rows[0]
    assert 'Job Title' in headers
    assert headers.index('Job Title') == headers.index('Company') + 1

    rows_by_code = {row[headers.index('Order code')]: row for row in rows[1:]}
    job_idx = headers.index('Job Title')
    assert rows_by_code['ORD01'][job_idx] == 'Staff Engineer'
    assert rows_by_code['ORD02'][job_idx] == 'Principal Architect'


@pytest.mark.django_db
def test_csv_checkin_list_exports_job_title_and_respects_column_selection(event):
    with scope(organizer=event.organizer, event=event), translation.override('en'):
        checkin_list = event.checkin_lists.create(name='Main Entrance', all_products=True)
        ticket = Product.objects.create(
            event=event, name='Standard Ticket', default_price=Decimal('25.00'), admission=True
        )
        addon = Product.objects.create(event=event, name='VIP Lounge', default_price=Decimal('0.00'), admission=False)

        order = create_paid_order(event, 'CHK01')
        base_pos = OrderPosition.objects.create(
            order=order,
            positionid=1,
            product=ticket,
            price=Decimal('25.00'),
            attendee_name_parts={'full_name': 'Linus Torvalds', '_scheme': 'full'},
            company='Kernel Org',
            job_title='DevOps Lead',
        )
        OrderPosition.objects.create(
            order=order,
            positionid=2,
            product=addon,
            addon_to=base_pos,
            price=Decimal('0.00'),
        )

        exporter = CSVCheckinList(event)
        column_keys = [key for key, _label in exporter._fields['columns'].choices]
        assert 'job_title' in column_keys
        assert column_keys.index('job_title') == column_keys.index('company') + 1
        assert 'job_title' in exporter._fields['columns'].initial

        default_rows = [
            row
            for row in exporter.iterate_list({'list': checkin_list.pk, 'questions': []})
            if not isinstance(row, exporter.ProgressSetTotal)
        ]
        filtered_rows = [
            row
            for row in exporter.iterate_list(
                {
                    'list': checkin_list.pk,
                    'questions': [],
                    'columns': ['order_code', 'attendee_name'],
                }
            )
            if not isinstance(row, exporter.ProgressSetTotal)
        ]

    headers = default_rows[0]
    assert 'Job title' in headers
    assert headers.index('Job title') == headers.index('Company') + 1

    job_idx = headers.index('Job title')
    assert [row[job_idx] for row in default_rows[1:]] == ['DevOps Lead', 'DevOps Lead']
    assert 'Job title' not in filtered_rows[0]


@pytest.mark.django_db
def test_pdf_checkin_list_exports_escaped_job_title(event):
    with scope(organizer=event.organizer, event=event), translation.override('en'):
        checkin_list = event.checkin_lists.create(name='Stage Door', all_products=True)
        ticket = Product.objects.create(
            event=event, name='Speaker Ticket', default_price=Decimal('25.00'), admission=True
        )
        order = create_paid_order(event, 'PDF01')
        InvoiceAddress.objects.create(
            order=order,
            name_parts={'full_name': 'Margaret Hamilton', '_scheme': 'full'},
        )
        OrderPosition.objects.create(
            order=order,
            positionid=1,
            product=ticket,
            price=Decimal('25.00'),
            attendee_name_parts={'full_name': 'Margaret Hamilton', '_scheme': 'full'},
            company='MIT Lab',
            job_title='R&D <Director>',
        )

        exporter = PDFCheckinList(event)
        form_data = {
            'list': checkin_list.pk,
            'questions': [],
            'columns': ['order_code', 'company', 'job_title'],
        }

        PDFCheckinList.register_fonts()
        story = exporter.get_story(SimpleNamespace(width=500), form_data)
        table = story[-1]
        header_texts = [getattr(cell, 'text', cell) for cell in table._cellvalues[0]]
        row_texts = [getattr(cell, 'text', cell) for cell in table._cellvalues[1]]

        _, content_type, pdf_bytes = exporter.render(form_data)

    assert 'Job title' in header_texts
    job_col = header_texts.index('Job title')
    assert row_texts[job_col] == 'R&amp;D &lt;Director&gt;'
    assert content_type == 'application/pdf'
    assert pdf_bytes.startswith(b'%PDF-')
