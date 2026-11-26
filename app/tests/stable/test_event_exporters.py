import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django import forms
from django.core.files.base import ContentFile
from django.db import models
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.exporter import EXPORTER_CATEGORIES, BaseExporter
from eventyay.base.i18n import language
from eventyay.base.models import (
    Checkin,
    CheckinList,
    Order,
    OrderPayment,
    OrderPosition,
    Product,
    Question,
    QuestionAnswer,
    Quota,
)
from eventyay.base.services.invoices import generate_invoice
from eventyay.base.signals import register_data_exporters
from eventyay.control.forms.orders import ExporterForm
from eventyay.control.views.orders import group_exporters
from eventyay.plugins.badges.models import BadgeLayout


PLUGINS = (
    'eventyay.plugins.banktransfer,eventyay.plugins.ticketoutputpdf,eventyay.plugins.badges,'
    'eventyay.plugins.checkinlists,eventyay.plugins.reports'
)
# dekodi is the only built-in export for an external tool, so it is listed under "Advanced / integrations".
ADVANCED_EXPORTERS = {'dekodi_nrei'}


@pytest.fixture
def sample_event(event):
    event.plugins = PLUGINS
    event.save()
    with scope(organizer=event.organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=Decimal('23.00'))
        quota = Quota.objects.create(event=event, name='Tickets', size=100)
        quota.products.add(product)
        order = Order.objects.create(
            code='EXPRT',
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PAID,
            datetime=now() - timedelta(days=1),
            expires=now() + timedelta(days=10),
            total=Decimal('23.00'),
            locale='en',
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('23.00'),
            attendee_name_parts={'_scheme': 'full', 'full_name': 'Jane Doe'},
            attendee_email='jane@example.com',
        )
        order.payments.create(
            amount=order.total,
            provider='banktransfer',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            payment_date=now(),
        )
        checkin_list = CheckinList.objects.create(event=event, name='Entrance', all_products=True)
        Checkin.objects.create(position=position, list=checkin_list)
        question = Question.objects.create(event=event, question='Photo', type=Question.TYPE_FILE)
        answer = QuestionAnswer.objects.create(orderposition=position, question=question, answer='file://photo.png')
        answer.file.save('photo.png', ContentFile(b'photo'))
        generate_invoice(order)
        BadgeLayout.objects.create(event=event, name='Default', default=True)
    return event


def form_data(field):
    """The value a visitor would submit for the field without changing it."""
    value = field.initial() if callable(field.initial) else field.initial
    if isinstance(field, forms.ModelMultipleChoiceField):
        return [obj.pk for obj in (value or field.queryset)]
    if isinstance(field, forms.ModelChoiceField):
        if isinstance(value, models.Model):
            return value.pk
        return value if value is not None else field.queryset.values_list('pk', flat=True).first()
    if isinstance(field, forms.MultipleChoiceField):
        return value if value is not None else []
    if isinstance(field, forms.ChoiceField) and isinstance(value, (list, tuple)):
        # A select shows the first value of a list as selected.
        value = value[0] if value else None
    if isinstance(field, forms.ChoiceField) and value in (None, ''):
        for key, label in field.choices:
            # In a group of options, the label is the list of options.
            option = label[0][0] if isinstance(label, (list, tuple)) else key
            if option not in (None, ''):
                return option
    return value if value is not None else ''


def render_export(exporter):
    form = ExporterForm(data={name: form_data(field) for name, field in exporter.export_form_fields.items()})
    form.fields = exporter.export_form_fields
    assert form.is_valid(), form.errors
    return exporter.render(form.cleaned_data)


@pytest.mark.django_db
def test_every_export_runs_on_a_sample_event(sample_event):
    # Runs every export with its default options the way the export task does, so a broken export
    # fails here instead of when an organizer downloads it.
    failures = {}
    with scope(organizer=sample_event.organizer), language('en'):
        exporters = [response(sample_event) for _, response in register_data_exporters.send(sample_event)]
        assert len(exporters) >= 20
        for exporter in exporters:
            try:
                filename, content_type, data = render_export(exporter)
            except Exception as e:  # noqa: BLE001
                failures[exporter.identifier] = repr(e)
                continue
            if not filename or not data:
                failures[exporter.identifier] = 'returned an empty file'
    assert not failures, '\n'.join(f'{identifier}: {error}' for identifier, error in sorted(failures.items()))


@pytest.mark.django_db
def test_built_in_exports_have_a_group_help_text_and_file_type(sample_event):
    categories = {key for key, label in EXPORTER_CATEGORIES}
    with scope(organizer=sample_event.organizer):
        for _, response in register_data_exporters.send(sample_event):
            exporter = response(sample_event)
            assert exporter.description, exporter.identifier
            assert exporter.file_type, exporter.identifier
            if exporter.identifier in ADVANCED_EXPORTERS:
                assert exporter.category is None
            else:
                assert exporter.category in categories, exporter.identifier


@pytest.mark.django_db
def test_exports_without_a_known_group_are_listed_as_advanced(event):
    class PluginExporter(BaseExporter):
        identifier = 'pluginexport'
        verbose_name = 'Plugin export'

    class OtherPluginExporter(PluginExporter):
        identifier = 'otherpluginexport'
        verbose_name = 'Another plugin export'
        category = 'unknown'

    class AttendeeExporter(PluginExporter):
        identifier = 'pluginattendees'
        verbose_name = 'Plugin attendees'
        category = 'attendees_orders'

    groups, advanced = group_exporters([PluginExporter(event), OtherPluginExporter(event), AttendeeExporter(event)])

    assert [group['category'] for group in groups] == [key for key, label in EXPORTER_CATEGORIES]
    assert [e.identifier for e in groups[0]['exporters']] == ['pluginattendees']
    assert [e.identifier for e in advanced] == ['otherpluginexport', 'pluginexport']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_export_page_shows_groups_in_order(organizer_client, sample_event):
    response = organizer_client.get(
        reverse(
            'control:event.orders.import_export',
            kwargs={'organizer': sample_event.organizer.slug, 'event': sample_event.slug},
        )
    )
    assert response.status_code == 200
    content = response.content.decode()

    headings = ['Attendees &amp; orders', 'Payments &amp; accounting', 'Check-in &amp; on-site']
    headings += ['Vouchers, waiting list &amp; availability', 'Advanced / integrations (1)']
    positions = [content.index(heading) for heading in headings]
    assert positions == sorted(positions)
    # The first exports of the first group, in the order of the issue, with help text and file type.
    names = [f'export-panel-name">{name}</h3>' for name in ('Attendee list', 'Orders', 'Email addresses')]
    assert [content.index(name) for name in names] == sorted(content.index(name) for name in names)
    assert 'One row per ticket, with attendee name, email, product and answers.' in content
    assert '<span class="export-panel-file-type">Excel / CSV</span>' in content
    # The advanced group is collapsed unless one export was requested.
    assert re.search(r'<details class="export-group export-group-advanced"\s*>', content)
