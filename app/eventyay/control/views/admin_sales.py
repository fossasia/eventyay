import csv
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, CharField, Count, DecimalField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from django_scopes import scope

from eventyay.base.models import BillingInvoice, Event, Order, OrderPosition
from eventyay.control.permissions import AdministratorPermissionRequiredMixin


EVENT_STATUSES = (('active', _('Active')), ('completed', _('Completed')), ('draft', _('Draft')))
INVOICE_STATUSES = (
    (BillingInvoice.STATUS_PENDING, _('Due')),
    (BillingInvoice.STATUS_PAID, _('Paid')),
    (BillingInvoice.STATUS_EXPIRED, _('Overdue')),
    (BillingInvoice.STATUS_CANCELED, _('Canceled')),
    (BillingInvoice.STATUS_REFUNDING, _('Refunding')),
    (BillingInvoice.STATUS_REFUNDED, _('Refunded')),
    (BillingInvoice.STATUS_FAILED, _('Failed')),
    (BillingInvoice.STATUS_RESOLVED, _('Resolved')),
)
EVENT_COLUMNS = (
    ('name', _('Event Name')),
    ('organizer__name', _('Organizer')),
    ('tickets_sold', _('Total Tickets Sold')),
    ('revenue', _('Revenue Generated')),
    ('currency', _('Currency')),
    ('date_from', _('Event Date')),
    ('sales_status', _('Status')),
)
INVOICE_COLUMNS = (
    ('id', _('Invoice Number')),
    ('event__name', _('Event Name')),
    ('created_at', _('Invoice Date')),
    ('due_date', _('Due Date')),
    ('final_ticket_fee', _('Amount')),
    ('currency', _('Currency')),
    ('sent_to_email', _('Sent to Email')),
    ('status', _('Status')),
)


def csv_response(filename: str, headers, rows) -> HttpResponse:
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow([str(header) for header in headers])
    for row in rows:
        # Untrusted names and email addresses must not become spreadsheet formulas.
        writer.writerow(
            [
                "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value
                for value in row
            ]
        )
    return response


class SalesOverview(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/sales/index.html'
    invoices = False

    def get(self, request, *args, **kwargs):
        # This report intentionally spans tenants, after the administrator session check.
        with scope(event=None, organizer=None):
            queryset = self.get_queryset()
            if request.GET.get('export') == 'csv':
                return csv_response(
                    'organizer-invoices' if self.invoices else 'event-performance',
                    [label for key, label in self.columns],
                    self.export_rows(queryset),
                )
            page = Paginator(queryset, 25).get_page(request.GET.get('page'))
            return self.render_to_response(
                self.get_context_data(
                    page_obj=page,
                    is_paginated=page.has_other_pages(),
                    rows=list(page),
                    columns=self.columns,
                    invoices=self.invoices,
                    statuses=INVOICE_STATUSES if self.invoices else EVENT_STATUSES,
                    query=request.GET.get('query', ''),
                    status=request.GET.get('status', ''),
                    ordering=self.ordering,
                )
            )

    def get_queryset(self):
        self.columns = INVOICE_COLUMNS if self.invoices else EVENT_COLUMNS
        query = self.request.GET.get('query', '').strip()
        if self.invoices:
            queryset = BillingInvoice.objects.select_related('event', 'organizer')
            search = Q(event__name__icontains=query)
            search |= Q(organizer__name__icontains=query)
            search |= Q(sent_to_email__icontains=query)
            if query.isascii() and query.isdecimal() and len(query) <= 18:
                search |= Q(pk=int(query))
        else:
            # Separate subqueries prevent order totals from being multiplied by ticket joins.
            paid_orders = Order.objects.filter(event=OuterRef('pk'), status=Order.STATUS_PAID)
            tickets = (
                OrderPosition.objects.filter(
                    order__event=OuterRef('pk'),
                    order__status=Order.STATUS_PAID,
                    canceled=False,
                    product__admission=True,
                )
                .order_by()
                .values('order__event')
                .annotate(total=Count('pk'))
                .values('total')
            )
            revenue = paid_orders.order_by().values('event').annotate(total=Sum('total')).values('total')
            queryset = Event.objects.select_related('organizer').annotate(
                tickets_sold=Coalesce(Subquery(tickets), 0),
                revenue=Coalesce(Subquery(revenue), Value(Decimal('0')), output_field=DecimalField()),
                sales_status=Case(
                    When(Q(date_to__lt=now()) | Q(date_to__isnull=True, date_from__lt=now()), then=Value('completed')),
                    When(live=True, then=Value('active')),
                    default=Value('draft'),
                    output_field=CharField(),
                ),
            )
            search = Q(name__icontains=query)
            search |= Q(organizer__name__icontains=query)
        queryset = queryset.filter(search)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(**{'status' if self.invoices else 'sales_status': status})
        ordering = self.request.GET.get('ordering', '-created_at' if self.invoices else '-date_from')
        allowed = {key for key, label in self.columns}
        allowed |= {f'-{key}' for key in allowed}
        if ordering not in allowed:
            ordering = '-created_at' if self.invoices else '-date_from'
        self.ordering = ordering
        # The due date is always one calendar month after creation.
        db_ordering = ordering.replace('due_date', 'created_at')
        return queryset.order_by(db_ordering, 'pk')

    def export_rows(self, queryset):
        for row in queryset.iterator(chunk_size=500):
            if self.invoices:
                yield (
                    row.pk,
                    str(row.event.name),
                    row.created_at.isoformat(),
                    row.due_date.isoformat(),
                    row.final_ticket_fee,
                    row.currency,
                    row.sent_to_email,
                    str(dict(INVOICE_STATUSES)[row.status]),
                )
            else:
                yield (
                    str(row.name),
                    row.organizer.name,
                    row.tickets_sold,
                    row.revenue,
                    row.currency,
                    row.date_from.isoformat(),
                    str(dict(EVENT_STATUSES)[row.sales_status]),
                )


class InvoiceStatusUpdate(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        status = request.POST.get('status')
        if status not in dict(INVOICE_STATUSES):
            return HttpResponseBadRequest(_('Invalid invoice status.'))
        with scope(organizer=None):
            invoice = get_object_or_404(BillingInvoice.objects.select_related('event', 'organizer'), pk=pk)
        with transaction.atomic(), scope(event=invoice.event, organizer=invoice.organizer):
            invoice = BillingInvoice.objects.select_for_update().get(pk=pk)
            if request.POST.get('previous_status') != invoice.status:
                return HttpResponse(_('The invoice changed. Reload the page and try again.'), status=409)
            if status != invoice.status:
                previous_status = invoice.status
                invoice.status = status
                invoice.updated_by = request.user.email[:50]
                invoice.paid_datetime = now() if status == BillingInvoice.STATUS_PAID else invoice.paid_datetime
                invoice.reminder_enabled = False
                invoice.automatic_payment_enabled = False
                invoice.save(
                    update_fields=[
                        'status',
                        'updated_by',
                        'updated_at',
                        'paid_datetime',
                        'reminder_enabled',
                        'automatic_payment_enabled',
                    ]
                )
                invoice.log_action(
                    'eventyay.billing.invoice.status_changed',
                    user=request.user,
                    data={
                        'old_status': previous_status,
                        'new_status': status,
                    },
                )
        messages.success(request, _('Invoice status updated. No charge or refund was initiated.'))
        return redirect('eventyay_admin:admin.sales.invoices')


class InvoicePaymentDetail(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/sales/payment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        with scope(organizer=None):
            invoice = get_object_or_404(
                BillingInvoice.objects.select_related('event', 'organizer'), pk=self.kwargs['pk']
            )
        context['invoice'] = invoice
        context['invoice_status'] = dict(INVOICE_STATUSES)[invoice.status]
        return context
