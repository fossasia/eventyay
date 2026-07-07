import logging
from collections import OrderedDict, defaultdict
from datetime import date, datetime, time, timedelta

import dateutil.parser
import nh3
from django import forms
from django.conf import settings
from django.db.models import (
    Case,
    Exists,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, NullIf
from django.template.defaultfilters import truncatechars, truncatechars_html
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.timezone import is_aware, make_aware
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, pgettext
from pytz import UTC
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from eventyay.base.exporter import BaseExporter, ListExporter
from eventyay.base.exporters.date import build_date_filter, parse_date_input
from eventyay.base.models import (
    Checkin,
    InvoiceAddress,
    Order,
    OrderPosition,
    Question,
)
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.base.templatetags.money import money_filter
from eventyay.control.forms.widgets import Select2
from eventyay.plugins.reports.exporters import ReportlabExportMixin

from ...helpers.templatetags.jsonfield import JSONExtract

logger = logging.getLogger(__name__)
# Minimum content width for a column in the PDF export
# before it is truncated. This is used to prevent columns from being too narrow.
MIN_CONTENT_WIDTH = 5
# When the content is too long for the column, we truncate it by this many characters.
# This is used to prevent the content from being too long and overflowing the column.
TRUNCATE_STEP_LENGTH = 50


class CheckInListMixin(BaseExporter):
    @property
    def _fields(self):
        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme]
        d = OrderedDict(
            [
                (
                    'list',
                    forms.ModelChoiceField(
                        queryset=self.event.checkin_lists.all(),
                        label=_('Check-in list'),
                        widget=forms.RadioSelect(attrs={'class': 'scrolling-choice'}),
                        initial=self.event.checkin_lists.first(),
                    ),
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
                    'secrets',
                    forms.BooleanField(label=_('Include QR-code secret'), required=False),
                ),
                (
                    'attention_only',
                    forms.BooleanField(
                        label=_('Only tickets requiring special attention'),
                        required=False,
                    ),
                ),
                (
                    'sort',
                    forms.ChoiceField(
                        label=_('Sort by'),
                        initial='name',
                        choices=[
                            ('name', _('Attendee name')),
                            ('code', _('Order code')),
                        ]
                        + (
                            [
                                (
                                    'name:{}'.format(k),
                                    _('Attendee name: {part}').format(part=label),
                                )
                                for k, label, w in name_scheme['fields']
                            ]
                            if len(name_scheme['fields']) > 1
                            else []
                        ),
                        widget=forms.RadioSelect,
                        required=False,
                    ),
                ),
                (
                    'columns',
                    forms.MultipleChoiceField(
                        label=_('Export columns'),
                        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
                        choices=[
                            ('order_code', _('Order code')),
                            ('attendee_name', _('Attendee name')),
                            ('product', _('Product')),
                            ('price', _('Price')),
                            ('auto_checked_in', _('Automatically checked in')),
                            ('status', _('Status (Paid)')),
                            ('email', _('E-mail')),
                            ('phone', _('Phone number')),
                            ('company', _('Company')),
                            ('voucher', _('Voucher code')),
                            ('order_date', _('Order date')),
                            ('requires_attention', _('Requires special attention')),
                            ('comment', _('Comment')),
                            ('seat', _('Seat details')),
                            ('address', _('Address')),
                            ('timestamp', _('Timestamp (Check-in and Check-out)')),
                        ],
                        initial=[
                            'order_code', 'attendee_name', 'product', 'price',
                            'auto_checked_in', 'status', 'email', 'phone', 'company', 'voucher',
                            'order_date', 'requires_attention', 'comment', 'seat', 'address',
                            'timestamp'
                        ],
                        required=False,
                    ),
                ),
                (
                    'questions',
                    forms.ModelMultipleChoiceField(
                        queryset=self.event.questions.all(),
                        label=_('Include questions'),
                        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
                        required=False,
                    ),
                ),
            ]
        )

        if not self.event.has_subevents:
            del d['date_from']
            del d['date_to']

        d['list'].queryset = self.event.checkin_lists.all()
        d['list'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.orders.checkinlists.select2',
                    kwargs={
                        'event': self.event.slug,
                        'organizer': self.event.organizer.slug,
                    },
                ),
                'data-placeholder': _('Check-in list'),
            }
        )
        d['list'].widget.choices = d['list'].choices
        d['list'].required = True

        return d

    def _get_queryset(self, cl, form_data):
        cqs = (
            Checkin.objects.filter(position_id=OuterRef('pk'), list_id=cl.pk)
            .order_by()
            .values('position_id')
            .annotate(m=Max('datetime'))
            .values('m')
        )

        cqsin = cqs.filter(type=Checkin.TYPE_ENTRY)
        cqsout = cqs.filter(type=Checkin.TYPE_EXIT)

        qs = (
            OrderPosition.objects.filter(
                order__event=self.event,
            )
            .annotate(
                last_checked_in=Subquery(cqsin),
                last_checked_out=Subquery(cqsout),
                auto_checked_in=Exists(
                    Checkin.objects.filter(position_id=OuterRef('pk'), list_id=cl.pk, auto_checked_in=True)
                ),
            )
            .prefetch_related(
                'answers',
                'answers__question',
                'addon_to__answers',
                'addon_to__answers__question',
            )
            .select_related(
                'order',
                'product',
                'variation',
                'addon_to',
                'order__invoice_address',
                'voucher',
                'seat',
            )
        )

        if not cl.all_products:
            qs = qs.filter(product__in=cl.limit_products.values_list('id', flat=True))

        if cl.subevent:
            qs = qs.filter(subevent=cl.subevent)

        if form_data.get('date_from'):
            date_from = parse_date_input(form_data['date_from'])
            qs = qs.filter(build_date_filter(date_from, None, self.event.tz))

        if form_data.get('date_to'):
            date_to = parse_date_input(form_data['date_to'])
            qs = qs.filter(build_date_filter(None, date_to, self.event.tz))

        o = ()
        if self.event.has_subevents and not cl.subevent:
            o = ('subevent__date_from', 'subevent__name')

        sort = form_data.get('sort') or 'name'
        if sort == 'name':
            qs = qs.order_by(
                *o,
                Coalesce(
                    NullIf('attendee_name_cached', Value('')),
                    NullIf('addon_to__attendee_name_cached', Value('')),
                    NullIf('order__invoice_address__name_cached', Value('')),
                    'order__code',
                ),
            )
        elif sort == 'code':
            qs = qs.order_by(*o, 'order__code')
        elif sort.startswith('name:'):
            part = sort[5:]
            qs = (
                qs.annotate(
                    resolved_name=Case(
                        When(attendee_name_cached__ne='', then='attendee_name_parts'),
                        When(
                            addon_to__attendee_name_cached__isnull=False,
                            addon_to__attendee_name_cached__ne='',
                            then='addon_to__attendee_name_parts',
                        ),
                        default='order__invoice_address__name_parts',
                    )
                )
                .annotate(resolved_name_part=JSONExtract('resolved_name', part))
                .order_by(*o, 'resolved_name_part')
            )

        if form_data.get('attention_only'):
            qs = qs.filter(Q(product__checkin_attention=True) | Q(order__checkin_attention=True))

        if not cl.include_pending:
            qs = qs.filter(order__status=Order.STATUS_PAID)
        else:
            qs = qs.filter(order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING))

        return qs


class CBFlowable(Flowable):
    def __init__(self, checked=False):
        self.checked = checked
        super().__init__()

    def draw(self):
        self.canv.rect(1 * mm, -4.5 * mm, 4 * mm, 4 * mm)
        if self.checked:
            self.canv.line(1.5 * mm, -4.0 * mm, 4.5 * mm, -1.0 * mm)
            self.canv.line(1.5 * mm, -1.0 * mm, 4.5 * mm, -4.0 * mm)


class TableTextRotate(Flowable):
    def __init__(self, text):
        Flowable.__init__(self)
        self.text = text

    def draw(self):
        canvas = self.canv
        canvas.rotate(90)
        canvas.drawString(0, -1, self.text)


class PDFCheckinList(ReportlabExportMixin, CheckInListMixin, BaseExporter):
    name = 'overview'
    identifier = 'checkinlistpdf'
    verbose_name = gettext_lazy('Check-in list (PDF)')

    @property
    def export_form_fields(self):
        f = self._fields
        del f['secrets']
        # We are exporting to PDF, which has limited space, so we tell user not to create too many columns.
        f['questions'].help_text = _(
            'Please do not pick too many questions, as they may not fit within the PDF page width.'
        )
        return f

    @property
    def pagesize(self):
        from reportlab.lib import pagesizes

        return pagesizes.landscape(pagesizes.A4)

    def get_story(self, doc, form_data):
        if 'list' not in form_data or not form_data['list']:
            # Return empty story instead of None
            return [Paragraph("No check-in list selected.", self.get_style())]
        cl = self.event.checkin_lists.get(pk=form_data['list'])

        questions = tuple(Question.objects.filter(event=self.event, id__in=form_data.get('questions', [])))

        columns = form_data.get('columns')
        if not columns:
            columns = [c[0] for c in self._fields['columns'].choices]

        headlinestyle = self.get_style()
        headlinestyle.fontSize = 15
        headlinestyle.fontName = 'OpenSansBd'
        
        fixed_colwidths = []
        headers = []
        if 'requires_attention' in columns:
            fixed_colwidths.append(3 * mm)
            headers.append('')
            
        fixed_colwidths.append(8 * mm) # Checkbox
        headers.append('')
            
        if cl.include_pending and 'status' in columns:
            fixed_colwidths.append(8 * mm)
            headers.append(TableTextRotate(pgettext('tablehead', 'paid')))

        dynamic_cols = [c for c in columns if c not in ['requires_attention', 'status']]
        
        weights = {
            'order_code': 0.1,
            'attendee_name': 0.25,
            'product': 0.25,
            'price': 0.1,
            'timestamp': 0.2,
            'auto_checked_in': 0.1,
            'email': 0.2,
            'phone': 0.15,
            'company': 0.15,
            'voucher': 0.1,
            'order_date': 0.15,
            'comment': 0.2,
            'seat': 0.15,
            'address': 0.25,
        }
        
        total_weight = sum(weights.get(c, 0.1) for c in dynamic_cols) + (0.35 if questions else 0)
        total_weight = total_weight or 1.0
        
        dyn_colwidths = []
        header_map = {
            'order_code': _('Order'),
            'attendee_name': _('Name'),
            'product': _('Product'),
            'price': _('Price'),
            'timestamp': _('Timestamp'),
            'auto_checked_in': _('Auto check-in'),
            'email': _('E-mail'),
            'phone': _('Phone'),
            'company': _('Company'),
            'voucher': _('Voucher'),
            'order_date': _('Order date'),
            'comment': _('Comment'),
            'seat': _('Seat'),
            'address': _('Address'),
        }
        
        num_cols = len(fixed_colwidths) + len(dynamic_cols) + len(questions)
        if num_cols > 12:
            font_size = 6
        elif num_cols > 8:
            font_size = 8
        else:
            font_size = 10

        headrowstyle = self.get_style()
        headrowstyle.fontName = 'OpenSansBd'
        headrowstyle.wordWrap = 'CJK'
        headrowstyle.fontSize = font_size
        for c in dynamic_cols:
            w = weights.get(c, 0.1)
            headers.append(Paragraph(str(header_map.get(c, c)), headrowstyle))
            dyn_colwidths.append((w / total_weight) * (doc.width - sum(fixed_colwidths)))
            
        colwidths = fixed_colwidths + dyn_colwidths
        
        for q in questions:
            w = 0.35 / len(questions)
            colwidths.append((w / total_weight) * (doc.width - sum(fixed_colwidths)))
            
        tdata = [headers]

        tstyledata = [
            ('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'OpenSansBd'),
            ('FONTSIZE', (0, 0), (-1, -1), font_size),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]
        
        current_idx = 0
        if 'requires_attention' in columns:
            tstyledata += [
                ('ALIGN', (current_idx, 0), (current_idx, -1), 'CENTER'),
                ('TEXTCOLOR', (current_idx, 0), (current_idx, -1), '#990000'),
                ('FONTNAME', (current_idx, 0), (current_idx, -1), 'OpenSansBd'),
            ]
            current_idx += 1
            
        tstyledata.append(('ALIGN', (current_idx, 0), (current_idx, -1), 'CENTER'))
        current_idx += 1
        
        status_col_idx = None
        if cl.include_pending and 'status' in columns:
            status_col_idx = current_idx
            tstyledata.append(('ALIGN', (status_col_idx, 0), (status_col_idx, 0), 'CENTER'))
            current_idx += 1

        story = [
            Paragraph(cl.name, headlinestyle),
        ]
        if cl.subevent:
            story += [
                Spacer(1, 3 * mm),
                Paragraph(
                    '{} ({} {})'.format(
                        cl.subevent.name,
                        cl.subevent.get_date_range_display(),
                        date_format(cl.subevent.date_from, 'TIME_FORMAT'),
                    ),
                    self.get_style(),
                ),
            ]

        story += [Spacer(1, 5 * mm)]

        headrowstyle = self.get_style()
        headrowstyle.fontName = 'OpenSansBd'
        for q in questions:
            text_or_html = str(q.question)
            p = Paragraph(text_or_html, headrowstyle)
            while (
                p.wrap(colwidths[len(tdata[0])], 5000)[1] > 30 * mm
                and get_visual_length(text_or_html) > MIN_CONTENT_WIDTH
            ):
                if nh3.is_html(text_or_html):
                    new_visual_length = max(MIN_CONTENT_WIDTH, get_visual_length(text_or_html) - TRUNCATE_STEP_LENGTH)
                    text_or_html = truncatechars_html(text_or_html, new_visual_length)
                else:
                    new_visual_length = max(MIN_CONTENT_WIDTH, get_visual_length(text_or_html) - TRUNCATE_STEP_LENGTH)
                    text_or_html = truncatechars(text_or_html, new_visual_length)
                p = Paragraph(text_or_html, headrowstyle)
            tdata[0].append(p)

        qs = self._get_queryset(cl, form_data)

        for op in qs:
            try:
                ian = op.order.invoice_address.name
                iac = op.order.invoice_address.company
            except AttributeError as e:
                logger.error('Error accessing invoice address for order position %s: %s', op.pk, e)
                ian = ''
                iac = ''

            name = op.attendee_name or (op.addon_to.attendee_name if op.addon_to else '') or ian
            if iac:
                name += '<br/>' + iac

            item = '{} ({})'.format(
                str(op.product) + (' – ' + str(op.variation.value) if op.variation else ''),
                money_filter(op.price, self.event.currency),
            )
            if self.event.has_subevents and not cl.subevent:
                item += '<br/>{} ({})'.format(
                    op.subevent.name,
                    date_format(
                        op.subevent.date_from.astimezone(self.event.tz),
                        'SHORT_DATETIME_FORMAT',
                    ),
                )
            if op.seat:
                item += '<br/>' + str(op.seat)
            row = []
            if 'requires_attention' in columns:
                row.append('!!' if op.product.checkin_attention or op.order.checkin_attention else '')
                
            row.append(CBFlowable(bool(op.last_checked_in)))
            
            if cl.include_pending and 'status' in columns:
                row.append('✘' if op.order.status != Order.STATUS_PAID else '✔')
                
            rowstyle = self.get_style()
            rowstyle.wordWrap = 'CJK'
            rowstyle.fontSize = font_size
            
            for c in dynamic_cols:
                if c == 'order_code':
                    row.append(Paragraph(op.order.code, rowstyle))
                elif c == 'attendee_name':
                    row.append(Paragraph(name, rowstyle))
                elif c == 'product':
                    row.append(Paragraph(item, rowstyle))
                elif c == 'price':
                    row.append(Paragraph(str(money_filter(op.price, self.event.currency)), rowstyle))
                elif c == 'timestamp':
                    ts = []
                    if op.last_checked_in:
                        ts.append(date_format(op.last_checked_in.astimezone(self.event.tz), 'SHORT_DATETIME_FORMAT'))
                    if op.last_checked_out:
                        ts.append(date_format(op.last_checked_out.astimezone(self.event.tz), 'SHORT_DATETIME_FORMAT'))
                    row.append(Paragraph('<br/>'.join(ts) if ts else '', rowstyle))
                elif c == 'auto_checked_in':
                    row.append(Paragraph(str(_('Yes') if op.auto_checked_in else _('No')), rowstyle))
                elif c == 'email':
                    row.append(Paragraph(op.attendee_email or (op.addon_to.attendee_email if op.addon_to else '') or op.order.email or '', rowstyle))
                elif c == 'phone':
                    row.append(Paragraph(str(op.order.phone) if op.order.phone else '', rowstyle))
                elif c == 'company':
                    row.append(Paragraph(op.company or iac, rowstyle))
                elif c == 'voucher':
                    row.append(Paragraph(op.voucher.code if op.voucher else '', rowstyle))
                elif c == 'order_date':
                    row.append(Paragraph(op.order.datetime.astimezone(self.event.tz).strftime('%Y-%m-%d'), rowstyle))
                elif c == 'comment':
                    row.append(Paragraph(op.order.comment or '', rowstyle))
                elif c == 'seat':
                    row.append(Paragraph(str(op.seat) if op.seat else '', rowstyle))
                elif c == 'address':
                    addr = [op.street, op.zipcode, op.city, op.country, op.state]
                    addr = [x for x in addr if x]
                    row.append(Paragraph('<br/>'.join(addr), rowstyle))
                else:
                    row.append(Paragraph('', rowstyle))

            acache = {}
            if op.addon_to:
                for a in op.addon_to.answers.all():
                    if a.question.type in Question.UNLOCALIZED_TYPES:
                        acache[a.question_id] = a.answer
                    else:
                        acache[a.question_id] = str(a)
            for a in op.answers.all():
                if a.question.type in Question.UNLOCALIZED_TYPES:
                    acache[a.question_id] = a.answer
                else:
                    acache[a.question_id] = str(a)
            for q in questions:
                text_or_html = acache.get(q.pk, '')
                p = Paragraph(text_or_html, self.get_style())
                while (
                    p.wrap(colwidths[len(row)], 5000)[1] > 50 * mm
                    and get_visual_length(text_or_html) > MIN_CONTENT_WIDTH
                ):
                    if nh3.is_html(text_or_html):
                        new_visual_length = max(
                            MIN_CONTENT_WIDTH, get_visual_length(text_or_html) - TRUNCATE_STEP_LENGTH
                        )
                        text_or_html = truncatechars_html(text_or_html, new_visual_length)
                    else:
                        new_visual_length = max(
                            MIN_CONTENT_WIDTH, get_visual_length(text_or_html) - TRUNCATE_STEP_LENGTH
                        )
                        text_or_html = truncatechars(text_or_html, new_visual_length)
                    p = Paragraph(text_or_html, self.get_style())
                row.append(p)
            if op.order.status != Order.STATUS_PAID and status_col_idx is not None:
                tstyledata += [
                    ('BACKGROUND', (status_col_idx, len(tdata)), (status_col_idx, len(tdata)), '#990000'),
                    ('TEXTCOLOR', (status_col_idx, len(tdata)), (status_col_idx, len(tdata)), '#ffffff'),
                    ('ALIGN', (status_col_idx, len(tdata)), (status_col_idx, len(tdata)), 'CENTER'),
                ]
            tdata.append(row)

        logger.debug('To create table with %s rows and %s columns', len(tdata), len(tdata[0]))
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        story.append(table)
        return story


class CSVCheckinList(CheckInListMixin, ListExporter):
    name = 'overview'
    identifier = 'checkinlist'
    verbose_name = gettext_lazy('Check-in list')

    @property
    def additional_form_fields(self):
        return self._fields

    @staticmethod
    def _format_checkin_datetime(dt, tz):
        if isinstance(dt, str):
            dt = dateutil.parser.parse(dt)
        elif not dt:
            return ''
        if not is_aware(dt):
            dt = make_aware(dt, UTC)
        return date_format(dt.astimezone(tz), 'SHORT_DATETIME_FORMAT')

    def _csv_row_for_position(
        self,
        op,
        ia,
        name_scheme,
        questions,
        cl,
        form_data,
        *,
        checkin=None,
    ):
        columns = form_data.get('columns')
        if not columns:
            columns = [c[0] for c in self._fields['columns'].choices]

        if checkin:
            checked_in = (
                self._format_checkin_datetime(checkin.datetime, self.event.tz)
                if checkin.type == Checkin.TYPE_ENTRY
                else ''
            )
            checked_out = (
                self._format_checkin_datetime(checkin.datetime, self.event.tz)
                if checkin.type == Checkin.TYPE_EXIT
                else ''
            )
            auto_checked_in = _('Yes') if checkin.auto_checked_in else _('No')
        else:
            checked_in = ''
            checked_out = ''
            auto_checked_in = _('Yes') if op.auto_checked_in else _('No')

        row = []
        if 'order_code' in columns:
            row.append(op.order.code)
        if 'attendee_name' in columns:
            row.append(op.attendee_name or (op.addon_to.attendee_name if op.addon_to else '') or ia.name)
            if len(name_scheme['fields']) > 1:
                for k, label, w in name_scheme['fields']:
                    row.append(
                        (
                            op.attendee_name_parts
                            or (op.addon_to.attendee_name_parts if op.addon_to else {})
                            or ia.name_parts
                        ).get(k, '')
                    )
        if 'product' in columns:
            row.append(str(op.product) + (' – ' + str(op.variation.value) if op.variation else ''))
        if 'price' in columns:
            row.append(op.price)
        if 'auto_checked_in' in columns:
            row.append(auto_checked_in)
        
        if cl.include_pending and 'status' in columns:
            row.append(_('Yes') if op.order.status == Order.STATUS_PAID else _('No'))
            
        if form_data.get('secrets'):
            row.append(op.secret)
        if 'email' in columns:
            row.append(op.attendee_email or (op.addon_to.attendee_email if op.addon_to else '') or op.order.email or '')
        if 'phone' in columns:
            row.append(str(op.order.phone) if op.order.phone else '')
        if self.event.has_subevents:
            row.append(str(op.subevent.name))
            row.append(
                date_format(
                    op.subevent.date_from.astimezone(self.event.tz),
                    'SHORT_DATETIME_FORMAT',
                )
            )
            if op.subevent.date_to:
                row.append(
                    date_format(
                        op.subevent.date_to.astimezone(self.event.tz),
                        'SHORT_DATETIME_FORMAT',
                    )
                )
            else:
                row.append('')
        
        acache = {}
        if op.addon_to:
            for a in op.addon_to.answers.all():
                if a.question.type in Question.UNLOCALIZED_TYPES:
                    acache[a.question_id] = a.answer
                else:
                    acache[a.question_id] = str(a)
        for a in op.answers.all():
            if a.question.type in Question.UNLOCALIZED_TYPES:
                acache[a.question_id] = a.answer
            else:
                acache[a.question_id] = str(a)
        for q in questions:
            row.append(acache.get(q.pk, ''))

        if 'company' in columns:
            row.append(op.company or ia.company)
        if 'voucher' in columns:
            row.append(op.voucher.code if op.voucher else '')
        if 'order_date' in columns:
            row.append(op.order.datetime.astimezone(self.event.tz).strftime('%Y-%m-%d'))
            row.append(op.order.datetime.astimezone(self.event.tz).strftime('%H:%M:%S %Z'))
        if 'requires_attention' in columns:
            row.append(_('Yes') if op.order.checkin_attention or op.product.checkin_attention else _('No'))
        if 'comment' in columns:
            row.append(op.order.comment or '')

        if 'seat' in columns:
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

        if 'address' in columns:
            row += [
                op.street or '',
                op.zipcode or '',
                op.city or '',
                op.country if op.country else '',
                op.state or '',
            ]
            
        if 'timestamp' in columns:
            row.append(checked_in)
            row.append(checked_out)

        return row

    def iterate_list(self, form_data):
        cl = self.event.checkin_lists.get(pk=form_data['list'])

        questions = list(Question.objects.filter(event=self.event, id__in=form_data['questions']))

        qs = self._get_queryset(cl, form_data)

        columns = form_data.get('columns')
        if not columns:
            columns = [c[0] for c in self._fields['columns'].choices]

        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme]
        headers = []
        if 'order_code' in columns:
            headers.append(_('Order code'))
        if 'attendee_name' in columns:
            headers.append(_('Attendee name'))
            if len(name_scheme['fields']) > 1:
                for k, label, w in name_scheme['fields']:
                    headers.append(_('Attendee name: {part}').format(part=label))
        if 'product' in columns:
            headers.append(_('Product'))
        if 'price' in columns:
            headers.append(_('Price'))

        if 'auto_checked_in' in columns:
            headers.append(_('Automatically checked in'))
        
        if not cl.include_pending:
            qs = qs.filter(order__status=Order.STATUS_PAID)
        else:
            qs = qs.filter(order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING))
            if 'status' in columns:
                headers.append(_('Paid'))

        if form_data.get('secrets'):
            headers.append(_('Secret'))

        if 'email' in columns:
            headers.append(_('E-mail'))
        if 'phone' in columns:
            headers.append(_('Phone number'))

        if self.event.has_subevents:
            headers.append(pgettext('subevent', 'Date'))
            headers.append(_('Start date'))
            headers.append(_('End date'))

        for q in questions:
            headers.append(str(q.question))

        if 'company' in columns:
            headers.append(_('Company'))
        if 'voucher' in columns:
            headers.append(_('Voucher code'))
        if 'order_date' in columns:
            headers.append(_('Order date'))
            headers.append(_('Order time'))
        if 'requires_attention' in columns:
            headers.append(_('Requires special attention'))
        if 'comment' in columns:
            headers.append(_('Comment'))
        if 'seat' in columns:
            headers.append(_('Seat ID'))
            headers.append(_('Seat name'))
            headers.append(_('Seat zone'))
            headers.append(_('Seat row'))
            headers.append(_('Seat number'))
        if 'address' in columns:
            headers += [
                _('Address'),
                _('ZIP code'),
                _('City'),
                _('Country'),
                pgettext('address', 'State'),
            ]
            
        if 'timestamp' in columns:
            headers.append(_('Checked in'))
            headers.append(_('Checked out'))
        yield headers

        positions = list(qs)
        checkins_by_position = defaultdict(list)
        if positions:
            for ci in Checkin.objects.filter(
                list=cl,
                position_id__in=[op.pk for op in positions],
            ).order_by('datetime', 'pk'):
                checkins_by_position[ci.position_id].append(ci)

        total_rows = sum(len(checkins_by_position.get(op.pk, [])) or 1 for op in positions)
        yield self.ProgressSetTotal(total=total_rows)

        for op in positions:
            try:
                ia = op.order.invoice_address
            except InvoiceAddress.DoesNotExist:
                ia = InvoiceAddress()

            checkins = checkins_by_position.get(op.pk, [])
            if not checkins:
                yield self._csv_row_for_position(
                    op,
                    ia,
                    name_scheme,
                    questions,
                    cl,
                    form_data,
                )
                continue

            for checkin in checkins:
                yield self._csv_row_for_position(
                    op,
                    ia,
                    name_scheme,
                    questions,
                    cl,
                    form_data,
                    checkin=checkin,
                )

    def get_filename(self):
        return '{}_checkin'.format(self.event.slug)


class CheckinLogList(ListExporter):
    name = 'checkinlog'
    identifier = 'checkinlog'
    verbose_name = gettext_lazy('Check-in log (all successful scans)')

    @property
    def additional_form_fields(self):
        return self._fields

    def iterate_list(self, form_data):
        yield [
            _('Date'),
            _('Time'),
            _('Check-in list'),
            _('Scan type'),
            _('Order code'),
            _('Position ID'),
            _('Secret'),
            _('Product'),
            _('Name'),
            _('Device'),
            _('Offline override'),
            _('Automatically checked in'),
        ]

        qs = Checkin.objects.filter(
            list__event=self.event,
        )
        if form_data.get('list'):
            qs = qs.filter(list_id=form_data['list'])
        if form_data.get('products'):
            product_ids = form_data['products']
            if product_ids and len(product_ids) != self.event.products.count():
                qs = qs.filter(position__product_id__in=product_ids)

        yield self.ProgressSetTotal(total=qs.count())

        qs = qs.select_related(
            'position__product',
            'position__order',
            'position__order__invoice_address',
            'position',
            'list',
            'device',
        ).order_by('datetime', 'pk')
        for ci in qs.iterator():
            try:
                ia = ci.position.order.invoice_address
            except InvoiceAddress.DoesNotExist:
                ia = InvoiceAddress()

            yield [
                date_format(ci.datetime, 'SHORT_DATE_FORMAT'),
                date_format(ci.datetime, 'TIME_FORMAT'),
                str(ci.list),
                ci.get_type_display(),
                ci.position.order.code,
                ci.position.positionid,
                ci.position.secret,
                str(ci.position.product),
                ci.position.attendee_name or ia.name,
                str(ci.device),
                _('Yes') if ci.forced else _('No'),
                _('Yes') if ci.auto_checked_in else _('No'),
            ]

    def get_filename(self):
        return '{}_checkinlog'.format(self.event.slug)

    @property
    def _fields(self):
        d = OrderedDict(
            [
                (
                    'list',
                    forms.ModelChoiceField(
                        queryset=self.event.checkin_lists.all(),
                        label=_('Check-in list'),
                        widget=forms.RadioSelect(attrs={'class': 'scrolling-choice'}),
                    ),
                ),
                (
                    'products',
                    forms.ModelMultipleChoiceField(
                        queryset=self.event.products.all(),
                        label=_('Limit to products'),
                        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
                        initial=self.event.products.all(),
                    ),
                ),
            ]
        )

        d['list'].queryset = self.event.checkin_lists.all()
        d['list'].widget = Select2(
            attrs={
                'data-model-select2': 'generic',
                'data-select2-url': reverse(
                    'control:event.orders.checkinlists.select2',
                    kwargs={
                        'event': self.event.slug,
                        'organizer': self.event.organizer.slug,
                    },
                ),
                'data-placeholder': _('All check-in lists'),
            }
        )
        d['list'].widget.choices = d['list'].choices
        d['list'].required = False

        return d


def get_visual_length(text_or_html: str) -> int:
    if not nh3.is_html(text_or_html):
        return len(text_or_html)
    return len(nh3.clean(text_or_html, tags=frozenset()))
