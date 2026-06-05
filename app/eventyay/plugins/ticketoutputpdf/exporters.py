from collections import OrderedDict
import logging
from io import BytesIO

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from pypdf import PdfWriter

from eventyay.base.exporter import BaseExporter
from eventyay.base.i18n import language
from eventyay.base.models import Event, Order, OrderPosition
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.base.exporters.date import build_multi_event_date_filter, parse_date_input

from ...helpers.templatetags.jsonfield import JSONExtract
from .ticketoutput import PdfTicketOutput


logger = logging.getLogger(__name__)
class AllTicketsPDF(BaseExporter):
    name = 'alltickets'
    verbose_name = gettext_lazy('All PDF tickets in one file')
    identifier = 'pdfoutput_all_tickets'

    @property
    def export_form_fields(self):
        # For multi-event exports, self.event is None, so name_scheme should be None
        # Only access self.event when self.is_multievent is False
        if self.is_multievent or self.event is None:
            name_scheme = None
        else:
            try:
                name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme]
            except KeyError:
                logger.warning('Unknown name_scheme: %s', getattr(self.event.settings, 'name_scheme', None))
                name_scheme = None

        d = OrderedDict(
            [
                (
                    'include_pending',
                    forms.BooleanField(label=_('Include pending orders'), required=False),
                ),
                (
                    'date_from',
                    forms.DateField(
                        label=_('Start date'),
                        widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                        required=False,
                        help_text=_('Only include tickets for dates on or after this date.'),
                    ),
                ),
                (
                    'date_to',
                    forms.DateField(
                        label=_('End date'),
                        widget=forms.DateInput(attrs={'class': 'datepickerfield'}),
                        required=False,
                        help_text=_('Only include tickets for dates on or before this date.'),
                    ),
                ),
                (
                    'order_by',
                    forms.ChoiceField(
                        label=_('Sort by'),
                        choices=[
                            ('name', _('Attendee name')),
                            ('code', _('Order code')),
                            ('date', _('Event date')),
                        ]
                        + (
                            [
                                (
                                    'name:{}'.format(k),
                                    _('Attendee name: {part}').format(part=label),
                                )
                                for k, label, w in name_scheme['fields']
                            ]
                            if name_scheme and len(name_scheme['fields']) > 1
                            else []
                        ),
                    ),
                ),
            ]
        )

        if not self.is_multievent and self.event and not self.event.has_subevents:
            del d['date_from']
            del d['date_to']

        return d

    def render(self, form_data):
        merger = PdfWriter()
        qs = (
            OrderPosition.objects.filter(order__event__in=self.events)
            .prefetch_related('answers', 'answers__question')
            .select_related('order', 'product', 'variation', 'addon_to')
        )

        if form_data.get('include_pending'):
            qs = qs.filter(order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING])
        else:
            qs = qs.filter(order__status__in=[Order.STATUS_PAID])

        date_from = form_data.get('date_from')
        date_to = form_data.get('date_to')
        if date_from or date_to:
            date_from = parse_date_input(date_from)
            date_to = parse_date_input(date_to)

            if date_from or date_to:
                events = [event for event in (self.events if self.is_multievent else (self.event,)) if event is not None]
                if events:
                    date_filters = build_multi_event_date_filter(events, date_from, date_to)
                    if date_filters is not None:
                        qs = qs.filter(date_filters)

        if form_data.get('order_by') == 'name':
            qs = qs.order_by('attendee_name_cached', 'order__code')
        elif form_data.get('order_by') == 'code':
            qs = qs.order_by('order__code')
        elif form_data.get('order_by') == 'date':
            qs = qs.annotate(ed=Coalesce('subevent__date_from', 'order__event__date_from')).order_by(
                'ed', 'order__code'
            )
        elif form_data.get('order_by', '').startswith('name:'):
            part = form_data['order_by'][5:]
            qs = (
                qs.annotate(
                    resolved_name=Coalesce(
                        'attendee_name_parts',
                        'addon_to__attendee_name_parts',
                        'order__invoice_address__name_parts',
                    )
                )
                .annotate(resolved_name_part=JSONExtract('resolved_name', part))
                .order_by('resolved_name_part')
            )

        o = PdfTicketOutput(Event.objects.none())
        any_tickets = False
        for op in qs:
            if not op.generate_ticket:
                continue
            any_tickets = True
            if op.order.event != o.event:
                o = PdfTicketOutput(op.event)

            with language(op.order.locale, o.event.settings.region):
                layout = o.layout_map.get(
                    (op.product_id, op.order.sales_channel),
                    o.layout_map.get((op.product_id, 'web'), o.default_layout),
                )
                outbuffer = o._draw_page(layout, op, op.order)
                merger.append(ContentFile(outbuffer.read()))

        if not any_tickets:
            return None

        outbuffer = BytesIO()
        merger.write(outbuffer)
        merger.close()
        outbuffer.seek(0)

        if self.is_multievent:
            return (
                '{}_tickets.pdf'.format(self.events.first().organizer.slug),
                'application/pdf',
                outbuffer.read(),
            )
        else:
            return (
                '{}_tickets.pdf'.format(self.event.slug),
                'application/pdf',
                outbuffer.read(),
            )
