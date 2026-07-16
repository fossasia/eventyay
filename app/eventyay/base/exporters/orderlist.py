from collections import OrderedDict
from decimal import Decimal

import dateutil
import pytz
from django import forms
from django.db.models import (
    Case,
    CharField,
    Count,
    DateTimeField,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    When,
)
from django.db.models.functions import Coalesce, TruncDate
from django.dispatch import receiver
from django.utils.functional import cached_property
from django.utils.timezone import get_current_timezone, now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, pgettext

from eventyay.base.models import (
    GiftCard,
    GiftCardTransaction,
    Invoice,
    InvoiceAddress,
    Order,
    OrderPosition,
    Question,
    User,
)
from eventyay.base.models.orders import OrderFee, OrderPayment, OrderRefund
from eventyay.base.services.quotas import QuotaAvailability
from eventyay.base.settings import PERSON_NAME_SCHEMES

from ...control.forms.filter import get_all_payment_providers
from ...helpers import GroupConcat
from ...helpers.iter import chunked_iterable
from ..exporter import ListExporter, MultiSheetListExporter
from ..signals import (
    register_data_exporters,
    register_multievent_data_exporters,
)


class OrderListExporter(MultiSheetListExporter):
    identifier = 'orderlist'
    verbose_name = gettext_lazy('Order data')

    @cached_property
    def providers(self):
        return dict(get_all_payment_providers())

    @property
    def sheets(self):
        return (
            ('orders', _('Orders')),
            ('positions', _('Order positions')),
            ('fees', _('Order fees')),
        )

    @property
    def additional_form_fields(self):
        prefix = f'#id_{self.identifier}'
        d = [
            (
                'paid_only',
                forms.BooleanField(
                    label=_('Only paid orders'),
                    initial=True,
                    required=False,
                    widget=forms.CheckboxInput(
                        attrs={'data-inverse-dependency': f'{prefix}-approval_pending_only'}
                    ),
                ),
            ),
            (
                'approval_pending_only',
                forms.BooleanField(
                    label=_('Only approval pending orders'),
                    initial=False,
                    required=False,
                    widget=forms.CheckboxInput(attrs={'data-inverse-dependency': f'{prefix}-paid_only'}),
                ),
            ),
            (
                'include_payment_amounts',
                forms.BooleanField(
                    label=_('Include payment amounts'),
                    initial=False,
                    required=False,
                    widget=forms.CheckboxInput(
                        attrs={'data-inverse-dependency': f'{prefix}-approval_pending_only'}
                    ),
                ),
            ),
            (
                'group_multiple_choice',
                forms.BooleanField(
                    label=_('Show multiple choice answers grouped in one column'),
                    initial=False,
                    required=False,
                ),
            ),
            (
                'date_from',
                forms.DateField(
                    label=_('Start date'),
                    widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                    required=False,
                    help_text=_('Only include orders created on or after this date.'),
                ),
            ),
            (
                'date_to',
                forms.DateField(
                    label=_('End date'),
                    widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                    required=False,
                    help_text=_('Only include orders created on or before this date.'),
                ),
            ),
            (
                'event_date_from',
                forms.DateField(
                    label=_('Start event date'),
                    widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                    required=False,
                    help_text=_(
                        'Only include orders including at least one ticket for a date on or after this date. '
                        'Will also include other dates in case of mixed orders!'
                    ),
                ),
            ),
            (
                'event_date_to',
                forms.DateField(
                    label=_('End event date'),
                    widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                    required=False,
                    help_text=_(
                        'Only include orders including at least one ticket for a date on or after this date. '
                        'Will also include other dates in case of mixed orders!'
                    ),
                ),
            ),
        ]
        d = OrderedDict(d)
        if not self.is_multievent and not self.event.has_subevents:
            del d['event_date_from']
            del d['event_date_to']
        return d

    def _approval_pending_only(self, form_data: dict) -> bool:
        return bool(form_data.get('approval_pending_only', False))

    def _include_payment_amounts(self, form_data: dict) -> bool:
        return bool(form_data.get('include_payment_amounts') and not self._approval_pending_only(form_data))

    def _filter_orders_by_state(self, qs, form_data: dict, prefix: str = ''):
        if self._approval_pending_only(form_data):
            return qs.filter(
                **{
                    f'{prefix}status': Order.STATUS_PENDING,
                    f'{prefix}require_approval': True,
                }
            )
        if form_data.get('paid_only', True):
            return qs.filter(**{f'{prefix}status': Order.STATUS_PAID})
        return qs

    @staticmethod
    def _first_filled(*values):
        for value in values:
            if value not in (None, ''):
                return value
        return ''

    def _primary_order_position(self, order):
        positions = getattr(order, 'export_positions', [])
        for position in positions:
            if not position.canceled:
                return position
        return positions[0] if positions else None

    def _get_all_payment_methods(self, qs):
        pps = dict(get_all_payment_providers())
        return sorted(
            [
                (pp, pps[pp])
                for pp in set(
                    OrderPayment.objects.exclude(provider='free')
                    .filter(order__event__in=self.events)
                    .values_list('provider', flat=True)
                    .distinct()
                )
            ],
            key=lambda pp: pp[0],
        )

    def _get_all_tax_rates(self, qs):
        tax_rates = set(
            a
            for a in OrderFee.objects.filter(order__event__in=self.events)
            .values_list('tax_rate', flat=True)
            .distinct()
            .order_by()
        )
        tax_rates |= set(
            a
            for a in OrderPosition.objects.filter(order__event__in=self.events)
            .values_list('tax_rate', flat=True)
            .distinct()
            .order_by()
        )
        tax_rates = sorted(tax_rates)
        return tax_rates

    def iterate_sheet(self, form_data, sheet):
        if sheet == 'orders':
            return self.iterate_orders(form_data)
        elif sheet == 'positions':
            return self.iterate_positions(form_data)
        elif sheet == 'fees':
            return self.iterate_fees(form_data)

    @cached_property
    def event_object_cache(self):
        return {e.pk: e for e in self.events}

    def _date_filter(self, qs, form_data, rel):
        annotations = {}
        filters = {}

        if form_data.get('date_from'):
            date_value = form_data.get('date_from')
            if isinstance(date_value, str):
                date_value = dateutil.parser.parse(date_value).date()

            annotations['date'] = TruncDate(f'{rel}datetime')
            filters['date__gte'] = date_value

        if form_data.get('date_to'):
            date_value = form_data.get('date_to')
            if isinstance(date_value, str):
                date_value = dateutil.parser.parse(date_value).date()

            annotations['date'] = TruncDate(f'{rel}datetime')
            filters['date__lte'] = date_value

        if form_data.get('event_date_from'):
            date_value = form_data.get('event_date_from')
            if isinstance(date_value, str):
                date_value = dateutil.parser.parse(date_value).date()

            annotations['event_date_max'] = Case(
                When(
                    **{f'{rel}event__has_subevents': True},
                    then=Max(f'{rel}all_positions__subevent__date_from'),
                ),
                default=F(f'{rel}event__date_from'),
            )
            filters['event_date_max__gte'] = date_value

        if form_data.get('event_date_to'):
            date_value = form_data.get('event_date_to')
            if isinstance(date_value, str):
                date_value = dateutil.parser.parse(date_value).date()

            annotations['event_date_min'] = Case(
                When(
                    **{f'{rel}event__has_subevents': True},
                    then=Min(f'{rel}all_positions__subevent__date_from'),
                ),
                default=F(f'{rel}event__date_from'),
            )
            filters['event_date_min__lte'] = date_value

        if filters:
            return qs.annotate(**annotations).filter(**filters)
        return qs

    def iterate_orders(self, form_data: dict):
        p_date = (
            OrderPayment.objects.filter(
                order=OuterRef('pk'),
                state__in=(
                    OrderPayment.PAYMENT_STATE_CONFIRMED,
                    OrderPayment.PAYMENT_STATE_REFUNDED,
                ),
                payment_date__isnull=False,
            )
            .values('order')
            .annotate(m=Max('payment_date'))
            .values('m')
            .order_by()
        )
        p_providers = (
            OrderPayment.objects.filter(
                order=OuterRef('pk'),
                state__in=(
                    OrderPayment.PAYMENT_STATE_CONFIRMED,
                    OrderPayment.PAYMENT_STATE_REFUNDED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    OrderPayment.PAYMENT_STATE_CREATED,
                ),
            )
            .values('order')
            .annotate(m=GroupConcat('provider', delimiter=','))
            .values('m')
            .order_by()
        )
        i_numbers = (
            Invoice.objects.filter(
                order=OuterRef('pk'),
            )
            .values('order')
            .annotate(m=GroupConcat('full_invoice_no', delimiter=', '))
            .values('m')
            .order_by()
        )

        s = (
            OrderPosition.objects.filter(order=OuterRef('pk'))
            .order_by()
            .values('order')
            .annotate(k=Count('id'))
            .values('k')
        )

        # Always load wikimedia_username (lightweight data)
        wikimedia_query = User.objects.filter(email=OuterRef('email')).values('wikimedia_username')[:1]

        qs = (
            Order.objects.filter(event__in=self.events)
            .annotate(
                payment_date=Subquery(p_date, output_field=DateTimeField()),
                payment_providers=Subquery(p_providers, output_field=CharField()),
                invoice_numbers=Subquery(i_numbers, output_field=CharField()),
                pcnt=Subquery(s, output_field=IntegerField()),
                wikimedia_username=Subquery(wikimedia_query, output_field=CharField()),
            )
            .select_related('invoice_address')
            .prefetch_related(
                Prefetch(
                    'positions',
                    queryset=OrderPosition.objects.select_related('addon_to').order_by('positionid'),
                    to_attr='export_positions',
                )
            )
        )

        qs = self._date_filter(qs, form_data, rel='')

        qs = self._filter_orders_by_state(qs, form_data)
        tax_rates = self._get_all_tax_rates(qs)

        # Check if we need to include wikimedia_username in the export
        should_include_wikimedia = any(
            self.event_object_cache[event_id].settings.get('include_wikimedia_username', False)
            for event_id in self.event_object_cache.keys()
        )

        headers = [
            _('Event slug'),
            _('Order code'),
            _('Order total'),
            _('Status'),
            _('Email'),
        ]

        # Add wikimedia_username header if setting is enabled
        if should_include_wikimedia:
            headers.append(_('Wikimedia username'))

        headers += [
            _('Phone number'),
            _('Order date'),
            _('Order time'),
            _('Company'),
            _('Name'),
        ]

        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme] if not self.is_multievent else None
        if name_scheme and len(name_scheme['fields']) > 1:
            for k, label, w in name_scheme['fields']:
                headers.append(label)
        headers += [
            _('Address'),
            _('ZIP code'),
            _('City'),
            _('Country'),
            pgettext('address', 'State'),
            _('Custom address field'),
            _('VAT ID'),
            _('Date of last payment'),
            _('Fees'),
            _('Order locale'),
        ]

        for tr in tax_rates:
            headers += [
                _('Gross at {rate} % tax').format(rate=tr),
                _('Net at {rate} % tax').format(rate=tr),
                _('Tax value at {rate} % tax').format(rate=tr),
            ]

        headers.append(_('Invoice numbers'))
        headers.append(_('Sales channel'))
        headers.append(_('Requires special attention'))
        headers.append(_('Comment'))
        headers.append(_('Positions'))
        headers.append(_('Payment providers'))
        payment_methods = []
        if self._include_payment_amounts(form_data):
            payment_methods = self._get_all_payment_methods(qs)
            for id, vn in payment_methods:
                headers.append(_('Paid by {method}').format(method=vn))

        yield headers

        full_fee_sum_cache = {
            o['order__id']: o['grosssum']
            for o in OrderFee.objects.values('tax_rate', 'order__id').order_by().annotate(grosssum=Sum('value'))
        }
        fee_sum_cache = {
            (o['order__id'], o['tax_rate']): o
            for o in OrderFee.objects.values('tax_rate', 'order__id')
            .order_by()
            .annotate(taxsum=Sum('tax_value'), grosssum=Sum('value'))
        }
        if self._include_payment_amounts(form_data):
            payment_sum_cache = {
                (o['order__id'], o['provider']): o['grosssum']
                for o in OrderPayment.objects.values('provider', 'order__id')
                .order_by()
                .filter(
                    state__in=[
                        OrderPayment.PAYMENT_STATE_CONFIRMED,
                        OrderPayment.PAYMENT_STATE_REFUNDED,
                    ]
                )
                .annotate(grosssum=Sum('amount'))
            }
            refund_sum_cache = {
                (o['order__id'], o['provider']): o['grosssum']
                for o in OrderRefund.objects.values('provider', 'order__id')
                .order_by()
                .filter(
                    state__in=[
                        OrderRefund.REFUND_STATE_DONE,
                        OrderRefund.REFUND_STATE_TRANSIT,
                    ]
                )
                .annotate(grosssum=Sum('amount'))
            }
        sum_cache = {
            (o['order__id'], o['tax_rate']): o
            for o in OrderPosition.objects.values('tax_rate', 'order__id')
            .order_by()
            .annotate(taxsum=Sum('tax_value'), grosssum=Sum('price'))
        }

        yield self.ProgressSetTotal(total=qs.count())
        id_iterator = qs.order_by('datetime').values_list('pk', flat=True).iterator(chunk_size=1000)
        for ids in chunked_iterable(id_iterator, 1000):
            ids = list(ids)
            orders_by_id = {order.pk: order for order in qs.filter(id__in=ids)}
            for order_id in ids:
                order = orders_by_id[order_id]
                tz = pytz.timezone(self.event_object_cache[order.event_id].settings.timezone)
                row = [
                    self.event_object_cache[order.event_id].slug,
                    order.code,
                    order.total,
                    order.get_status_display(),
                    order.email,
                ]

                # Add wikimedia_username if setting is enabled (insert before phone number)
                if should_include_wikimedia:
                    wikimedia_username = getattr(order, 'wikimedia_username', '') or ''
                    row.append(wikimedia_username)

                row += [
                    str(order.phone) if order.phone else '',
                    order.datetime.astimezone(tz).strftime('%Y-%m-%d'),
                    order.datetime.astimezone(tz).strftime('%H:%M:%S %Z'),
                ]

                try:
                    invoice_address = order.invoice_address
                except InvoiceAddress.DoesNotExist:
                    invoice_address = None

                primary_position = self._primary_order_position(order)
                position_name_parts = {}
                if primary_position:
                    position_name_parts = primary_position.attendee_name_parts or {}
                    if not position_name_parts and primary_position.addon_to:
                        position_name_parts = primary_position.addon_to.attendee_name_parts or {}

                row += [
                    self._first_filled(
                        invoice_address.company if invoice_address else None,
                        primary_position.company if primary_position else None,
                        primary_position.addon_to.company if primary_position and primary_position.addon_to else None,
                    ),
                    self._first_filled(
                        invoice_address.name if invoice_address else None,
                        primary_position.attendee_name if primary_position else None,
                        primary_position.addon_to.attendee_name
                        if primary_position and primary_position.addon_to
                        else None,
                    ),
                ]
                if name_scheme and len(name_scheme['fields']) > 1:
                    for k, label, w in name_scheme['fields']:
                        row.append(
                            self._first_filled(
                                invoice_address.name_parts.get(k, '') if invoice_address else '',
                                position_name_parts.get(k, ''),
                            )
                        )
                row += [
                    self._first_filled(
                        invoice_address.street if invoice_address else None,
                        primary_position.street if primary_position else None,
                        primary_position.addon_to.street if primary_position and primary_position.addon_to else None,
                    ),
                    self._first_filled(
                        invoice_address.zipcode if invoice_address else None,
                        primary_position.zipcode if primary_position else None,
                        primary_position.addon_to.zipcode if primary_position and primary_position.addon_to else None,
                    ),
                    self._first_filled(
                        invoice_address.city if invoice_address else None,
                        primary_position.city if primary_position else None,
                        primary_position.addon_to.city if primary_position and primary_position.addon_to else None,
                    ),
                    self._first_filled(
                        invoice_address.country if invoice_address and invoice_address.country else None,
                        invoice_address.country_old if invoice_address else None,
                        primary_position.country if primary_position else None,
                        primary_position.addon_to.country if primary_position and primary_position.addon_to else None,
                    ),
                    self._first_filled(
                        invoice_address.state if invoice_address else None,
                        primary_position.state if primary_position else None,
                        primary_position.addon_to.state if primary_position and primary_position.addon_to else None,
                    ),
                    invoice_address.custom_field if invoice_address else '',
                    invoice_address.vat_id if invoice_address else '',
                ]

                row += [
                    order.payment_date.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z') if order.payment_date else '',
                    full_fee_sum_cache.get(order.id) or Decimal('0.00'),
                    order.locale,
                ]

                for tr in tax_rates:
                    taxrate_values = sum_cache.get(
                        (order.id, tr),
                        {'grosssum': Decimal('0.00'), 'taxsum': Decimal('0.00')},
                    )
                    fee_taxrate_values = fee_sum_cache.get(
                        (order.id, tr),
                        {'grosssum': Decimal('0.00'), 'taxsum': Decimal('0.00')},
                    )

                    row += [
                        taxrate_values['grosssum'] + fee_taxrate_values['grosssum'],
                        (
                            taxrate_values['grosssum']
                            - taxrate_values['taxsum']
                            + fee_taxrate_values['grosssum']
                            - fee_taxrate_values['taxsum']
                        ),
                        taxrate_values['taxsum'] + fee_taxrate_values['taxsum'],
                    ]

                row.append(order.invoice_numbers)
                row.append(order.sales_channel)
                row.append(_('Yes') if order.checkin_attention else _('No'))
                row.append(order.comment or '')
                row.append(order.pcnt)
                row.append(
                    ', '.join(
                        [
                            str(self.providers.get(p, p))
                            for p in sorted(set((order.payment_providers or '').split(',')))
                            if p and p != 'free'
                        ]
                    )
                )

                if self._include_payment_amounts(form_data):
                    for id, vn in payment_methods:
                        row.append(
                            payment_sum_cache.get((order.id, id), Decimal('0.00'))
                            - refund_sum_cache.get((order.id, id), Decimal('0.00'))
                        )
                yield row

    def iterate_fees(self, form_data: dict):
        p_providers = (
            OrderPayment.objects.filter(
                order=OuterRef('order'),
                state__in=(
                    OrderPayment.PAYMENT_STATE_CONFIRMED,
                    OrderPayment.PAYMENT_STATE_REFUNDED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    OrderPayment.PAYMENT_STATE_CREATED,
                ),
            )
            .values('order')
            .annotate(m=GroupConcat('provider', delimiter=','))
            .values('m')
            .order_by()
        )
        qs = (
            OrderFee.objects.filter(
                order__event__in=self.events,
            )
            .annotate(
                payment_providers=Subquery(p_providers, output_field=CharField()),
            )
            .select_related('order', 'order__invoice_address', 'tax_rule')
        )
        qs = self._filter_orders_by_state(qs, form_data, prefix='order__')

        qs = self._date_filter(qs, form_data, rel='order__')

        headers = [
            _('Event slug'),
            _('Order code'),
            _('Status'),
            _('Email'),
            _('Phone number'),
            _('Order date'),
            _('Order time'),
            _('Fee type'),
            _('Description'),
            _('Price'),
            _('Tax rate'),
            _('Tax rule'),
            _('Tax value'),
            _('Company'),
            _('Invoice address name'),
        ]
        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme] if not self.is_multievent else None
        if name_scheme and len(name_scheme['fields']) > 1:
            for k, label, w in name_scheme['fields']:
                headers.append(_('Invoice address name') + ': ' + str(label))
        headers += [
            _('Address'),
            _('ZIP code'),
            _('City'),
            _('Country'),
            pgettext('address', 'State'),
            _('VAT ID'),
        ]

        headers.append(_('Payment providers'))
        yield headers

        yield self.ProgressSetTotal(total=qs.count())
        for op in qs.order_by('order__datetime').iterator():
            order = op.order
            tz = pytz.timezone(order.event.settings.timezone)
            row = [
                self.event_object_cache[order.event_id].slug,
                order.code,
                order.get_status_display(),
                order.email,
                str(order.phone) if order.phone else '',
                order.datetime.astimezone(tz).strftime('%Y-%m-%d'),
                order.datetime.astimezone(tz).strftime('%H:%M:%S %Z'),
                op.get_fee_type_display(),
                op.description,
                op.value,
                op.tax_rate,
                str(op.tax_rule) if op.tax_rule else '',
                op.tax_value,
            ]
            try:
                row += [
                    order.invoice_address.company,
                    order.invoice_address.name,
                ]
                if name_scheme and len(name_scheme['fields']) > 1:
                    for k, label, w in name_scheme['fields']:
                        row.append(order.invoice_address.name_parts.get(k, ''))
                row += [
                    order.invoice_address.street,
                    order.invoice_address.zipcode,
                    order.invoice_address.city,
                    order.invoice_address.country
                    if order.invoice_address.country
                    else order.invoice_address.country_old,
                    order.invoice_address.state,
                    order.invoice_address.vat_id,
                ]
            except InvoiceAddress.DoesNotExist:
                row += [''] * (
                    8 + (len(name_scheme['fields']) if name_scheme and len(name_scheme['fields']) > 1 else 0)
                )
            row.append(
                ', '.join(
                    [
                        str(self.providers.get(p, p))
                        for p in sorted(set((op.payment_providers or '').split(',')))
                        if p and p != 'free'
                    ]
                )
            )
            yield row

    def iterate_positions(self, form_data: dict):
        p_providers = (
            OrderPayment.objects.filter(
                order=OuterRef('order'),
                state__in=(
                    OrderPayment.PAYMENT_STATE_CONFIRMED,
                    OrderPayment.PAYMENT_STATE_REFUNDED,
                    OrderPayment.PAYMENT_STATE_PENDING,
                    OrderPayment.PAYMENT_STATE_CREATED,
                ),
            )
            .values('order')
            .annotate(m=GroupConcat('provider', delimiter=','))
            .values('m')
            .order_by()
        )
        base_qs = OrderPosition.objects.filter(
            order__event__in=self.events,
        )
        qs = (
            base_qs.annotate(
                payment_providers=Subquery(p_providers, output_field=CharField()),
            )
            .select_related(
                'order',
                'order__invoice_address',
                'addon_to',
                'product',
                'variation',
                'voucher',
                'tax_rule',
            )
            .prefetch_related('answers', 'answers__question', 'answers__options')
        )
        qs = self._filter_orders_by_state(qs, form_data, prefix='order__')

        qs = self._date_filter(qs, form_data, rel='order__')

        has_subevents = self.events.filter(has_subevents=True).exists()

        headers = [
            _('Event slug'),
            _('Order code'),
            _('Position ID'),
            _('Status'),
            _('Email'),
            _('Phone number'),
            _('Order date'),
            _('Order time'),
        ]
        if has_subevents:
            headers.append(pgettext('subevent', 'Date'))
            headers.append(_('Start date'))
            headers.append(_('End date'))
        headers += [
            _('Product'),
            _('Variation'),
            _('Price'),
            _('Tax rate'),
            _('Tax rule'),
            _('Tax value'),
            _('Attendee name'),
        ]
        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme] if not self.is_multievent else None
        if name_scheme and len(name_scheme['fields']) > 1:
            for k, label, w in name_scheme['fields']:
                headers.append(_('Attendee name') + ': ' + str(label))
        headers += [
            _('Attendee email'),
            _('Company'),
            _('Job Title'),
            _('Address'),
            _('ZIP code'),
            _('City'),
            _('Country'),
            pgettext('address', 'State'),
            _('Voucher'),
            _('Pseudonymization ID'),
            _('Seat ID'),
            _('Seat name'),
            _('Seat zone'),
            _('Seat row'),
            _('Seat number'),
            _('Order comment'),
        ]

        questions = list(Question.objects.filter(event__in=self.events))
        options = {}
        for q in questions:
            if q.type == Question.TYPE_CHOICE_MULTIPLE:
                options[q.pk] = []
                if form_data.get('group_multiple_choice', False):
                    for o in q.options.all():
                        options[q.pk].append(o)
                    headers.append(str(q.question))
                else:
                    for o in q.options.all():
                        headers.append(str(q.question) + ' – ' + str(o.answer))
                        options[q.pk].append(o)
            else:
                headers.append(str(q.question))
        headers += [
            _('Company'),
            _('Invoice address name'),
        ]
        if name_scheme and len(name_scheme['fields']) > 1:
            for k, label, w in name_scheme['fields']:
                headers.append(_('Invoice address name') + ': ' + str(label))
        headers += [
            _('Address'),
            _('ZIP code'),
            _('City'),
            _('Country'),
            pgettext('address', 'State'),
            _('VAT ID'),
        ]
        headers += [
            _('Sales channel'),
            _('Order locale'),
            _('Payment providers'),
        ]

        try:
            from eventyay.plugins.badges.utils import get_badge_visible_field_labels
            badge_support = True
            headers.append(_('Badge options'))
        except ImportError:
            badge_support = False

        yield headers

        all_ids = list(base_qs.order_by('order__datetime', 'positionid').values_list('pk', flat=True))
        yield self.ProgressSetTotal(total=len(all_ids))
        for ids in chunked_iterable(all_ids, 1000):
            ops = sorted(qs.filter(id__in=ids), key=lambda k: ids.index(k.pk))

            for op in ops:
                order = op.order
                tz = pytz.timezone(self.event_object_cache[order.event_id].settings.timezone)
                try:
                    invoice_address = order.invoice_address
                except InvoiceAddress.DoesNotExist:
                    invoice_address = None

                person_source = op.attendee_name_parts or (op.addon_to.attendee_name_parts if op.addon_to else {})
                if not person_source and invoice_address:
                    person_source = invoice_address.name_parts

                row = [
                    self.event_object_cache[order.event_id].slug,
                    order.code,
                    op.positionid,
                    order.get_status_display(),
                    order.email,
                    str(order.phone) if order.phone else '',
                    order.datetime.astimezone(tz).strftime('%Y-%m-%d'),
                    order.datetime.astimezone(tz).strftime('%H:%M:%S %Z'),
                ]
                if has_subevents:
                    if op.subevent:
                        row.append(op.subevent.name)
                        row.append(
                            op.subevent.date_from.astimezone(self.event_object_cache[order.event_id].timezone).strftime(
                                '%Y-%m-%d %H:%M:%S %Z'
                            )
                        )
                        if op.subevent.date_to:
                            row.append(
                                op.subevent.date_to.astimezone(
                                    self.event_object_cache[order.event_id].timezone
                                ).strftime('%Y-%m-%d %H:%M:%S %Z')
                            )
                        else:
                            row.append('')
                    else:
                        row.append('')
                        row.append('')
                        row.append('')
                row += [
                    str(op.product),
                    str(op.variation) if op.variation else '',
                    op.price,
                    op.tax_rate,
                    str(op.tax_rule) if op.tax_rule else '',
                    op.tax_value,
                    op.attendee_name
                    or (op.addon_to.attendee_name if op.addon_to else '')
                    or (invoice_address.name if invoice_address else ''),
                ]
                if name_scheme and len(name_scheme['fields']) > 1:
                    for k, label, w in name_scheme['fields']:
                        row.append(person_source.get(k, ''))
                row += [
                    op.attendee_email or (op.addon_to.attendee_email if op.addon_to else '') or order.email or '',
                    op.company
                    or (op.addon_to.company if op.addon_to else '')
                    or (invoice_address.company if invoice_address else ''),
                    op.job_title or (op.addon_to.job_title if op.addon_to else ''),
                    op.street
                    or (op.addon_to.street if op.addon_to else '')
                    or (invoice_address.street if invoice_address else ''),
                    op.zipcode
                    or (op.addon_to.zipcode if op.addon_to else '')
                    or (invoice_address.zipcode if invoice_address else ''),
                    op.city
                    or (op.addon_to.city if op.addon_to else '')
                    or (invoice_address.city if invoice_address else ''),
                    op.country
                    or (op.addon_to.country if op.addon_to else '')
                    or (invoice_address.country if invoice_address else ''),
                    op.state
                    or (op.addon_to.state if op.addon_to else '')
                    or (invoice_address.state if invoice_address else ''),
                    op.voucher.code if op.voucher else '',
                    op.pseudonymization_id,
                ]

                if op.seat:
                    row += [
                        op.seat.seat_guid,
                        str(op.seat),
                        op.seat.zone_name,
                        op.seat.row_name,
                        op.seat.seat_number,
                    ]
                else:
                    row += ['', '', '', '', '']

                row.append(order.comment)
                acache = {}
                for a in op.answers.all():
                    # We do not want to localize Date, Time and Datetime question answers, as those can lead
                    # to difficulties parsing the data (for example 2019-02-01 may become Février, 2019 01 in French).
                    if a.question.type == Question.TYPE_CHOICE_MULTIPLE:
                        acache[a.question_id] = set(o.pk for o in a.options.all())
                    elif a.question.type in Question.UNLOCALIZED_TYPES:
                        acache[a.question_id] = a.answer
                    else:
                        acache[a.question_id] = str(a)
                for q in questions:
                    if q.type == Question.TYPE_CHOICE_MULTIPLE:
                        if form_data.get('group_multiple_choice', False):
                            row.append(
                                ', '.join(str(o.answer) for o in options[q.pk] if o.pk in acache.get(q.pk, set()))
                            )
                        else:
                            for o in options[q.pk]:
                                row.append(_('Yes') if o.pk in acache.get(q.pk, set()) else _('No'))
                    else:
                        row.append(acache.get(q.pk, ''))

                try:
                    row += [
                        order.invoice_address.company,
                        order.invoice_address.name,
                    ]
                    if name_scheme and len(name_scheme['fields']) > 1:
                        for k, label, w in name_scheme['fields']:
                            row.append(order.invoice_address.name_parts.get(k, ''))
                    row += [
                        order.invoice_address.street,
                        order.invoice_address.zipcode,
                        order.invoice_address.city,
                        order.invoice_address.country
                        if order.invoice_address.country
                        else order.invoice_address.country_old,
                        order.invoice_address.state,
                        order.invoice_address.vat_id,
                    ]
                except InvoiceAddress.DoesNotExist:
                    row += [''] * (
                        8 + (len(name_scheme['fields']) if name_scheme and len(name_scheme['fields']) > 1 else 0)
                    )
                row += [
                    order.sales_channel,
                    order.locale,
                ]
                row.append(
                    ', '.join(
                        [
                            str(self.providers.get(p, p))
                            for p in sorted(set((op.payment_providers or '').split(',')))
                            if p and p != 'free'
                        ]
                    )
                )

                if badge_support:
                    badge_labels = get_badge_visible_field_labels(self.event_object_cache[order.event_id], op)
                    row.append(', '.join(badge_labels) if badge_labels else '')

                yield row

    def get_filename(self):
        if self.is_multievent:
            return f'{self.events.first().organizer.slug}_orders'
        else:
            return f'{self.event.slug}_orders'


class OrderPositionListExporter(OrderListExporter):
    identifier = 'orderpositionlist'
    verbose_name = gettext_lazy('Order positions')

    @property
    def export_form_fields(self) -> dict:
        ff = OrderedDict(
            [
                (
                    '_format',
                    forms.ChoiceField(
                        label=_('Export format'),
                        choices=(
                            ('xlsx', _('Excel (.xlsx)')),
                            ('default', _('CSV (with commas)')),
                            ('csv-excel', _('CSV (Excel-style)')),
                            ('semicolon', _('CSV (with semicolons)')),
                        ),
                    ),
                ),
            ]
        )
        ff.update(self.additional_form_fields)
        return ff

    def iterate_list(self, form_data):
        yield from self.iterate_positions(form_data)

    def get_filename(self):
        if self.is_multievent:
            return f'{self.events.first().organizer.slug}_orderpositions'
        else:
            return f'{self.event.slug}_orderpositions'

    def render(self, form_data: dict, output_file=None):
        return super(MultiSheetListExporter, self).render(form_data, output_file=output_file)


class PaymentListExporter(ListExporter):
    identifier = 'paymentlist'
    verbose_name = gettext_lazy('Order payments and refunds')

    @property
    def additional_form_fields(self):
        return OrderedDict(
            [
                (
                    'payment_states',
                    forms.MultipleChoiceField(
                        label=_('Payment states'),
                        choices=OrderPayment.PAYMENT_STATES,
                        initial=[
                            OrderPayment.PAYMENT_STATE_CONFIRMED,
                            OrderPayment.PAYMENT_STATE_REFUNDED,
                        ],
                        required=False,
                        widget=forms.CheckboxSelectMultiple,
                    ),
                ),
                (
                    'refund_states',
                    forms.MultipleChoiceField(
                        label=_('Refund states'),
                        choices=OrderRefund.REFUND_STATES,
                        initial=[
                            OrderRefund.REFUND_STATE_DONE,
                            OrderRefund.REFUND_STATE_CREATED,
                            OrderRefund.REFUND_STATE_TRANSIT,
                        ],
                        widget=forms.CheckboxSelectMultiple,
                        required=False,
                    ),
                ),
            ]
        )

    def iterate_list(self, form_data):
        provider_names = dict(get_all_payment_providers())

        payments = OrderPayment.objects.filter(
            order__event__in=self.events, state__in=form_data.get('payment_states', [])
        ).order_by('created')
        refunds = OrderRefund.objects.filter(
            order__event__in=self.events, state__in=form_data.get('refund_states', [])
        ).order_by('created')

        objs = sorted(list(payments) + list(refunds), key=lambda o: o.created)

        headers = [
            _('Event slug'),
            _('Order'),
            _('Payment ID'),
            _('Creation date'),
            _('Completion date'),
            _('Status'),
            _('Status code'),
            _('Amount'),
            _('Payment method'),
            _('Comment'),
        ]
        yield headers

        yield self.ProgressSetTotal(total=len(objs))
        for obj in objs:
            tz = pytz.timezone(obj.order.event.settings.timezone)
            if isinstance(obj, OrderPayment) and obj.payment_date:
                d2 = obj.payment_date.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            elif isinstance(obj, OrderRefund) and obj.execution_date:
                d2 = obj.execution_date.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            else:
                d2 = ''
            row = [
                obj.order.event.slug,
                obj.order.code,
                obj.full_id,
                obj.created.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z'),
                d2,
                obj.get_state_display(),
                obj.state,
                obj.amount * (-1 if isinstance(obj, OrderRefund) else 1),
                provider_names.get(obj.provider, obj.provider),
                obj.comment if isinstance(obj, OrderRefund) else '',
            ]
            yield row

    def get_filename(self):
        if self.is_multievent:
            return f'{self.events.first().organizer.slug}_payments'
        else:
            return f'{self.event.slug}_payments'


class QuotaListExporter(ListExporter):
    identifier = 'quotalist'
    verbose_name = gettext_lazy('Quota availabilities')

    def iterate_list(self, form_data):
        has_subevents = self.event.has_subevents
        headers = [
            _('Quota name'),
            _('Total quota'),
            _('Paid orders'),
            _('Pending orders'),
            _('Blocking vouchers'),
            _("Current user's carts"),
            _('Waiting list'),
            _('Exited orders'),
            _('Current availability'),
        ]
        if has_subevents:
            headers.append(pgettext('subevent', 'Date'))
            headers.append(_('Start date'))
            headers.append(_('End date'))
        yield headers

        quotas = list(self.event.quotas.select_related('subevent'))
        qa = QuotaAvailability(full_results=True)
        qa.queue(*quotas)
        qa.compute()

        for quota in quotas:
            avail = qa.results[quota]
            row = [
                quota.name,
                _('Infinite') if quota.size is None else quota.size,
                qa.count_paid_orders[quota],
                qa.count_pending_orders[quota],
                qa.count_vouchers[quota],
                qa.count_cart[quota],
                qa.count_waitinglist[quota],
                qa.count_exited_orders[quota],
                _('Infinite') if avail[1] is None else avail[1],
            ]
            if has_subevents:
                if quota.subevent:
                    row.append(quota.subevent.name)
                    row.append(
                        quota.subevent.date_from.astimezone(self.event.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
                    )
                    if quota.subevent.date_to:
                        row.append(
                            quota.subevent.date_to.astimezone(self.event.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
                        )
                    else:
                        row.append('')
                else:
                    row.append('')
                    row.append('')
                    row.append('')
            yield row

    def get_filename(self):
        return f'{self.event.slug}_quotas'


class GiftcardRedemptionListExporter(ListExporter):
    identifier = 'giftcardredemptionlist'
    verbose_name = gettext_lazy('Gift card redemptions')

    def iterate_list(self, form_data):
        payments = OrderPayment.objects.filter(
            order__event__in=self.events,
            provider='giftcard',
            state__in=(
                OrderPayment.PAYMENT_STATE_CONFIRMED,
                OrderPayment.PAYMENT_STATE_REFUNDED,
            ),
        ).order_by('created')
        refunds = OrderRefund.objects.filter(
            order__event__in=self.events,
            provider='giftcard',
            state=OrderRefund.REFUND_STATE_DONE,
        ).order_by('created')

        objs = sorted(list(payments) + list(refunds), key=lambda o: (o.order.code, o.created))

        headers = [
            _('Event slug'),
            _('Order'),
            _('Payment ID'),
            _('Date'),
            _('Gift card code'),
            _('Amount'),
            _('Issuer'),
        ]
        yield headers

        for obj in objs:
            tz = pytz.timezone(obj.order.event.settings.timezone)
            gc = GiftCard.objects.get(pk=obj.info_data.get('gift_card'))
            row = [
                obj.order.event.slug,
                obj.order.code,
                obj.full_id,
                obj.created.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z'),
                gc.secret,
                obj.amount * (-1 if isinstance(obj, OrderRefund) else 1),
                gc.issuer,
            ]
            yield row

    def get_filename(self):
        if self.is_multievent:
            return f'{self.events.first().organizer.slug}_giftcardredemptions'
        else:
            return f'{self.event.slug}_giftcardredemptions'


def generate_GiftCardListExporter(organizer):  # hackhack
    class GiftcardListExporter(ListExporter):
        identifier = 'giftcardlist'
        verbose_name = gettext_lazy('Gift cards')

        @property
        def additional_form_fields(self):
            return OrderedDict(
                [
                    (
                        'date',
                        forms.DateTimeField(
                            label=_('Show value at'),
                            initial=now(),
                        ),
                    ),
                    (
                        'testmode',
                        forms.ChoiceField(
                            label=_('Test mode'),
                            choices=(
                                ('', _('All')),
                                ('yes', _('Test mode')),
                                ('no', _('Live')),
                            ),
                            initial='no',
                            required=False,
                        ),
                    ),
                    (
                        'state',
                        forms.ChoiceField(
                            label=_('Status'),
                            choices=(
                                ('', _('All')),
                                ('empty', _('Empty')),
                                ('valid_value', _('Valid and with value')),
                                ('expired_value', _('Expired and with value')),
                                ('expired', _('Expired')),
                            ),
                            initial='valid_value',
                            required=False,
                        ),
                    ),
                ]
            )

        def iterate_list(self, form_data):
            s = (
                GiftCardTransaction.objects.filter(card=OuterRef('pk'), datetime__lte=form_data['date'])
                .order_by()
                .values('card')
                .annotate(s=Sum('value'))
                .values('s')
            )
            qs = (
                organizer.issued_gift_cards.filter(issuance__lte=form_data['date'])
                .annotate(
                    cached_value=Coalesce(Subquery(s), Decimal('0.00')),
                )
                .order_by('issuance')
                .prefetch_related(
                    'transactions',
                    'transactions__order',
                    'transactions__order__event',
                    'transactions__order__invoices',
                )
            )

            if form_data.get('testmode') == 'yes':
                qs = qs.filter(testmode=True)
            elif form_data.get('testmode') == 'no':
                qs = qs.filter(testmode=False)

            if form_data.get('state') == 'empty':
                qs = qs.filter(cached_value=0)
            elif form_data.get('state') == 'valid_value':
                qs = qs.exclude(cached_value=0).filter(Q(expires__isnull=True) | Q(expires__gte=form_data['date']))
            elif form_data.get('state') == 'expired_value':
                qs = qs.exclude(cached_value=0).filter(expires__lt=form_data['date'])
            elif form_data.get('state') == 'expired':
                qs = qs.filter(expires__lt=form_data['date'])

            headers = [
                _('Gift card code'),
                _('Test mode card'),
                _('Creation date'),
                _('Expiry date'),
                _('Special terms and conditions'),
                _('Currency'),
                _('Current value'),
                _('Created in order'),
                _('Last invoice number of order'),
                _('Last invoice date of order'),
            ]
            yield headers

            tz = get_current_timezone()
            for obj in qs:
                o = None
                i = None
                trans = list(obj.transactions.all())
                if trans:
                    o = trans[0].order
                if o:
                    invs = list(o.invoices.all())
                    if invs:
                        i = invs[-1]
                row = [
                    obj.secret,
                    _('Yes') if obj.testmode else _('No'),
                    obj.issuance.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z'),
                    obj.expires.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S %Z') if obj.expires else '',
                    obj.conditions or '',
                    obj.currency,
                    obj.cached_value,
                    o.full_code if o else '',
                    i.number if i else '',
                    i.date.strftime('%Y-%m-%d') if i else '',
                ]
                yield row

        def get_filename(self):
            return f'{organizer.slug}_giftcards'

    return GiftcardListExporter


@receiver(register_data_exporters, dispatch_uid='exporter_orderlist')
def register_orderlist_exporter(sender, **kwargs):
    return OrderListExporter


@receiver(register_multievent_data_exporters, dispatch_uid='multiexporter_orderlist')
def register_multievent_orderlist_exporter(sender, **kwargs):
    return OrderListExporter


@receiver(register_data_exporters, dispatch_uid='exporter_orderpositionlist')
def register_orderpositionlist_exporter(sender, **kwargs):
    return OrderPositionListExporter


@receiver(register_multievent_data_exporters, dispatch_uid='multiexporter_orderpositionlist')
def register_multievent_orderpositionlist_exporter(sender, **kwargs):
    return OrderPositionListExporter


@receiver(register_data_exporters, dispatch_uid='exporter_paymentlist')
def register_paymentlist_exporter(sender, **kwargs):
    return PaymentListExporter


@receiver(register_multievent_data_exporters, dispatch_uid='multiexporter_paymentlist')
def register_multievent_paymentlist_exporter(sender, **kwargs):
    return PaymentListExporter


@receiver(register_data_exporters, dispatch_uid='exporter_quotalist')
def register_quotalist_exporter(sender, **kwargs):
    return QuotaListExporter


@receiver(register_data_exporters, dispatch_uid='exporter_giftcardredemptionlist')
def register_giftcardredemptionlist_exporter(sender, **kwargs):
    return GiftcardRedemptionListExporter


@receiver(
    register_multievent_data_exporters,
    dispatch_uid='multiexporter_giftcardredemptionlist',
)
def register_multievent_i_giftcardredemptionlist_exporter(sender, **kwargs):
    return GiftcardRedemptionListExporter


@receiver(register_multievent_data_exporters, dispatch_uid='multiexporter_giftcardlist')
def register_multievent_i_giftcardlist_exporter(sender, **kwargs):
    return generate_GiftCardListExporter(sender)
