import copy
import json
from collections import OrderedDict
from io import BytesIO
from typing import Tuple

from django import forms
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files import File
from django.core.files.storage import default_storage
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from pypdf import Transformation
from reportlab.lib import pagesizes
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from eventyay.base.exporter import BaseExporter
from eventyay.base.exporters.date import build_date_filter, parse_date_input
from eventyay.base.i18n import language
from eventyay.base.models import Order, OrderPosition
from eventyay.base.pdf import Renderer
from eventyay.base.services.orders import OrderError
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.plugins.badges.models import BadgeProduct, BadgeLayout
from eventyay.plugins.badges.utils import get_badge_hidden_fields, normalize_badge_content_key

from ...helpers.templatetags.jsonfield import JSONExtract


class BadgeRenderer(Renderer):
    def __init__(self, event, layout, bgf, ask_user_fields=None):
        super().__init__(event, layout, bgf)
        self.ask_user_fields = {str(value) for value in (ask_user_fields or [])}

    def _get_text_content(self, op: OrderPosition, order: Order, o: dict, inner=False):
        content = normalize_badge_content_key(o.get('content'))
        if content and content not in ('other', 'other_i18n') and content in self.ask_user_fields:
            hidden_fields = getattr(op, '_badge_hidden_fields_cache', None)
            if hidden_fields is None:
                hidden_fields = {str(value) for value in get_badge_hidden_fields(op)}
                op._badge_hidden_fields_cache = hidden_fields
            if content in hidden_fields:
                return ''

        if content != o.get('content'):
            o = dict(o)
            o['content'] = content

        return super()._get_text_content(op, order, o, inner=inner)


def _renderer(event, layout):
    if layout is None:
        return None
    if isinstance(layout.background, File) and layout.background.name:
        bgf = default_storage.open(layout.background.name, 'rb')
    else:
        bgf = open(finders.find('pretixplugins/badges/badge_default_a6l.pdf'), 'rb')
    return BadgeRenderer(
        event,
        layout.layout_data,
        bgf,
        ask_user_fields=(layout.ask_user_fields_data if layout.allow_customization else []),
    )


OPTIONS = OrderedDict(
    [
        (
            'one',
            {
                'name': gettext_lazy('One badge per page'),
                'cols': 1,
                'rows': 1,
                'margins': [0, 0, 0, 0],
                'offsets': [0, 0],
                'pagesize': None,
            },
        ),
        (
            'a4_a6l',
            {
                'name': gettext_lazy('4 landscape A6 pages on one A4 page'),
                'cols': 2,
                'rows': 2,
                'margins': [0 * mm, 0 * mm, 0 * mm, 0 * mm],
                'offsets': [
                    pagesizes.landscape(pagesizes.A4)[0] / 2,
                    pagesizes.landscape(pagesizes.A4)[1] / 2,
                ],
                'pagesize': pagesizes.landscape(pagesizes.A4),
            },
        ),
        (
            'a4_a6p',
            {
                'name': gettext_lazy('4 portrait A6 pages on one A4 page'),
                'cols': 2,
                'rows': 2,
                'margins': [0 * mm, 0 * mm, 0 * mm, 0 * mm],
                'offsets': [
                    pagesizes.portrait(pagesizes.A4)[0] / 2,
                    pagesizes.portrait(pagesizes.A4)[0] / 2,
                ],
                'pagesize': pagesizes.portrait(pagesizes.A4),
            },
        ),
        (
            'a4_a7l',
            {
                'name': gettext_lazy('8 landscape A7 pages on one A4 page'),
                'cols': 2,
                'rows': 4,
                'margins': [0 * mm, 0 * mm, 0 * mm, 0 * mm],
                'offsets': [
                    pagesizes.portrait(pagesizes.A4)[0] / 2,
                    pagesizes.portrait(pagesizes.A4)[1] / 4,
                ],
                'pagesize': pagesizes.portrait(pagesizes.A4),
            },
        ),
        (
            'a4_a7p',
            {
                'name': gettext_lazy('8 portrait A7 pages on one A4 page'),
                'cols': 4,
                'rows': 2,
                'margins': [0 * mm, 0 * mm, 0 * mm, 0 * mm],
                'offsets': [
                    pagesizes.landscape(pagesizes.A4)[0] / 4,
                    pagesizes.landscape(pagesizes.A4)[0] / 2,
                ],
                'pagesize': pagesizes.landscape(pagesizes.A4),
            },
        ),
        (
            'durable_54x90',
            {
                'name': 'DURABLE BADGEMAKER® 54 x 90 mm (1445-02)',
                'cols': 2,
                'rows': 5,
                'margins': [12 * mm, 15 * mm, 15 * mm, 15 * mm],
                'offsets': [90 * mm, 54 * mm],
                'pagesize': pagesizes.A4,
            },
        ),
        (
            'durable_40x75',
            {
                'name': 'DURABLE BADGEMAKER® 40 x 75 mm (1453-02)',
                'cols': 2,
                'rows': 6,
                'margins': [28.5 * mm, 30 * mm, 28.5 * mm, 30 * mm],
                'offsets': [75 * mm, 40 * mm],
                'pagesize': pagesizes.A4,
            },
        ),
        (
            'durable_60x90',
            {
                'name': 'DURABLE BADGEMAKER® 60 x 90 mm (1456-02)',
                'cols': 2,
                'rows': 4,
                'margins': [28.5 * mm, 15 * mm, 28.5 * mm, 15 * mm],
                'offsets': [90 * mm, 60 * mm],
                'pagesize': pagesizes.A4,
            },
        ),
        (
            'durable_fix_40x75',
            {
                'name': 'DURABLE BADGEFIX® 40 x 75 mm (8334-02)',
                'cols': 2,
                'rows': 6,
                'margins': [28.5 * mm, 30 * mm, 28.5 * mm, 30 * mm],
                'offsets': [93 * mm, 60 * mm],
                'pagesize': pagesizes.A4,
            },
        ),
        (
            'herma_50x80',
            {
                'name': 'HERMA 50 x 80 mm (4412)',
                'cols': 2,
                'rows': 5,
                'margins': [13.5 * mm, 17.5 * mm, 13.5 * mm, 17.5 * mm],
                'offsets': [95 * mm, 55 * mm],
                'pagesize': pagesizes.A4,
            },
        ),
    ]
)


def render_pdf(event, positions, opt):
    from pypdf import PdfReader, PdfWriter

    Renderer._register_fonts()

    renderermap = {
        bi.product_id: _renderer(event, bi.layout)
        for bi in BadgeProduct.objects.select_related('layout').filter(product__event=event)
    }
    try:
        default_renderer = _renderer(event, event.badge_layouts.get(default=True))
    except BadgeLayout.DoesNotExist:
        default_renderer = None
    output_pdf_writer = PdfWriter()

    any = False
    npp = opt['cols'] * opt['rows']

    def render_page(positions):
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=pagesizes.A4)
        for i, (op, r) in enumerate(positions):
            offsetx = opt['margins'][3] + (i % opt['cols']) * opt['offsets'][0]
            offsety = opt['margins'][2] + (opt['rows'] - 1 - i // opt['cols']) * opt['offsets'][1]
            p.translate(offsetx, offsety)
            with language(op.order.locale, op.order.event.settings.region):
                r.draw_page(p, op.order, op, show_page=False)
            p.translate(-offsetx, -offsety)

        if opt['pagesize']:
            p.setPageSize(opt['pagesize'])
        p.showPage()
        p.save()
        buffer.seek(0)
        canvas_pdf_reader = PdfReader(buffer)
        empty_pdf_page = output_pdf_writer.add_blank_page(
            width=opt['pagesize'][0] if opt['pagesize'] else positions[0][1].bg_pdf.pages[0].mediabox[2],
            height=opt['pagesize'][1] if opt['pagesize'] else positions[0][1].bg_pdf.pages[0].mediabox[3],
        )
        for i, (op, r) in enumerate(positions):
            bg_page = copy.copy(r.bg_pdf.pages[0])
            offsetx = opt['margins'][3] + (i % opt['cols']) * opt['offsets'][0]
            offsety = opt['margins'][2] + (opt['rows'] - 1 - i // opt['cols']) * opt['offsets'][1]
            bg_page.add_transformation(Transformation().translate(offsetx, offsety))
            empty_pdf_page.merge_page(bg_page)
        empty_pdf_page.merge_page(canvas_pdf_reader.pages[0])

    pagebuffer = []
    outbuffer = BytesIO()
    for op in positions:
        r = renderermap.get(op.product_id, default_renderer)
        if not r:
            continue
        any = True
        pagebuffer.append((op, r))
        if len(pagebuffer) == npp:
            render_page(pagebuffer)
            pagebuffer.clear()

    if pagebuffer:
        render_page(pagebuffer)

    if not any:
        raise OrderError(_('None of the selected products is configured to print badges.'))
    output_pdf_writer.add_metadata(
        {
            '/Title': 'Badges',
            '/Creator': 'eventyay',
        }
    )
    output_pdf_writer.write(outbuffer)
    outbuffer.seek(0)
    return outbuffer


class BadgeExporter(BaseExporter):
    identifier = 'badges'
    verbose_name = _('Attendee badges')

    @property
    def export_form_fields(self):
        name_scheme = PERSON_NAME_SCHEMES[self.event.settings.name_scheme]
        d = OrderedDict(
            [
                (
                    'products',
                    forms.ModelMultipleChoiceField(
                        queryset=self.event.products.annotate(
                            no_badging=Exists(BadgeProduct.objects.filter(product=OuterRef('pk'), layout__isnull=True))
                        ).exclude(no_badging=True),
                        label=_('Limit to products'),
                        widget=forms.CheckboxSelectMultiple(attrs={'class': 'scrolling-multiple-choice'}),
                        initial=self.event.products.filter(admission=True),
                    ),
                ),
                (
                    'include_pending',
                    forms.BooleanField(label=_('Include pending orders'), required=False),
                ),
                (
                    'include_addons',
                    forms.BooleanField(label=_('Include add-on or bundled positions'), required=False),
                ),
                (
                    'rendering',
                    forms.ChoiceField(
                        label=_('Rendering option'),
                        choices=[(k, r['name']) for k, r in OPTIONS.items()],
                        required=True,
                        help_text=_(
                            'This option allows you to align multiple badges on one page, for example if you '
                            'want to print to a sheet of stickers with a regular office printer. Please note '
                            'that your individual badge layouts must already be in the correct size.'
                        ),
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
                            if len(name_scheme['fields']) > 1
                            else []
                        ),
                    ),
                ),
            ]
        )
        return d

    def render(self, form_data: dict) -> Tuple[str, str, str]:
        qs = (
            OrderPosition.objects.filter(order__event=self.event, product_id__in=form_data['products'])
            .prefetch_related('answers', 'answers__question')
            .select_related('order', 'product', 'variation', 'addon_to')
        )

        if not form_data.get('include_addons'):
            qs = qs.filter(addon_to__isnull=True)

        if form_data.get('include_pending'):
            qs = qs.filter(order__status__in=[Order.STATUS_PAID, Order.STATUS_PENDING])
        else:
            qs = qs.filter(order__status__in=[Order.STATUS_PAID])

        if form_data.get('date_from'):
            date_from = parse_date_input(form_data['date_from'])
            qs = qs.filter(build_date_filter(date_from, None, self.event.tz))

        if form_data.get('date_to'):
            date_to = parse_date_input(form_data['date_to'])
            qs = qs.filter(build_date_filter(None, date_to, self.event.tz))

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

        outbuffer = render_pdf(self.event, qs, OPTIONS[form_data.get('rendering', 'one')])
        return 'badges.pdf', 'application/pdf', outbuffer.read()
