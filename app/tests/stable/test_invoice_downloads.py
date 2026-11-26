from datetime import timedelta
from decimal import Decimal
from zipfile import ZipFile

import pytest
from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import CachedFile, Order, OrderPosition, Product, Team
from eventyay.base.services.invoices import generate_invoice


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, SITE_URL='https://testserver')
def test_invoice_download_forms(client, event, organizer, user):
    team = Team.objects.create(organizer=organizer, name='Orders', all_events=True, can_view_orders=True)
    team.members.add(user)
    with scope(event=event, organizer=organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=Decimal('23.00'))
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='buyer@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('23.00'),
            locale='en',
        )
        OrderPosition.objects.create(order=order, product=product, price=Decimal('23.00'))
        invoice = generate_invoice(order)

    client.force_login(user)
    kwargs = {'event': event.slug, 'organizer': organizer.slug}
    page = client.get(reverse('control:event.orders.invoice_downloads', kwargs=kwargs))
    assert page.status_code == 200
    target = reverse('control:event.orders.import_export.export_do', kwargs=kwargs)
    forms = BeautifulSoup(page.content, 'html.parser').find_all('form', action=target)
    assert [form.select_one('[name=exporter]')['value'] for form in forms] == ['invoices', 'invoicedata']
    assert forms[1].find('input', attrs={'name': 'invoicedata-_format'})['value'] == 'xlsx'

    for form, member in zip(forms, [f'{invoice.number}-{order.code}.pdf', 'xl/workbook.xml'], strict=True):
        data = {field['name']: field['value'] for field in form.select('input[name]')}
        response = client.post(target, data)
        assert response.status_code == 302
        cached = CachedFile.objects.get(
            session_key=client.session.session_key,
            filename__endswith='.zip' if data['exporter'] == 'invoices' else '.xlsx',
        )
        assert response.url == reverse('cachedfile.download', kwargs={'id': cached.pk})
        with cached.file.open('rb') as output, ZipFile(output) as archive:
            assert member in archive.namelist()

    team.can_view_orders = False
    team.can_change_orders = False
    team.can_change_event_settings = True
    team.save()
    assert client.get(page.wsgi_request.path).status_code == 403
