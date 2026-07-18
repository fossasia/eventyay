import os
import tempfile
from collections import OrderedDict
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from django import forms
from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.files import File
from django.core.files.storage import default_storage
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from pypdf import PdfReader, PdfWriter, Transformation
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
from eventyay.plugins.badges.models import BadgeProduct, BadgeVoucher
from eventyay.plugins.badges.utils import (
    _renderer_cache,
    exclude_explicit_no_badge,
    get_badge_hidden_fields,
    get_badge_layout_for_position,
    get_badge_layout_version,
    normalize_badge_content_key,
)

from ...helpers.templatetags.jsonfield import JSONExtract

SEARCHABLE_SCROLLING_CHECKBOXES = 'scrolling-multiple-choice scrolling-multiple-choice-searchable'


def searchable_scrolling_checkbox_widget():
    return forms.CheckboxSelectMultiple(attrs={'class': SEARCHABLE_SCROLLING_CHECKBOXES})


class BadgeRenderer(Renderer):
    def __init__(self, event, layout, bgf, ask_user_fields=None):
        super().__init__(event, layout, bgf)
        self.ask_user_fields = {str(value) for value in (ask_user_fields or [])}

    def _get_layout_hidden_fields(self, op: OrderPosition):
        if not self.ask_user_fields:
            return set()

        hidden_fields = getattr(op, '_badge_hidden_fields_cache', None)
        if hidden_fields is None:
            hidden_fields = {str(value) for value in get_badge_hidden_fields(op)}
            op._badge_hidden_fields_cache = hidden_fields
        return {field for field in hidden_fields if field in self.ask_user_fields}

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


def _is_placeholder_pdf(bgf):
    pos = bgf.tell()
    try:
        bgf.seek(0, os.SEEK_END)
        size = bgf.tell()
        bgf.seek(pos)
        if size < 1_000:
            return True
        if size < 15_000:
            header = bgf.read(200)
            return b'ReportLab Generated PDF' in header
        return False
    finally:
        bgf.seek(pos)


def _bundled_background_for_layout(layout):
    media_dir = Path(settings.BASE_DIR) / 'plugins/badges/media'
    if not media_dir.is_dir():
        return None
    name_lower = layout.name.lower()
    for pdf_path in sorted(media_dir.glob('*.pdf')):
        if pdf_path.stem.lower() in name_lower:
            return open(pdf_path, 'rb')
    return None


def _open_layout_background(layout):
    if isinstance(layout.background, File) and layout.background.name:
        bgf = default_storage.open(layout.background.name, 'rb')
        if not _is_placeholder_pdf(bgf):
            return bgf
        bgf.close()
    bundled = _bundled_background_for_layout(layout)
    if bundled:
        return bundled
    return open(finders.find('pretixplugins/badges/badge_default_a6l.pdf'), 'rb')


def _renderer(event, layout, version):
    if layout is None:
        return None

    cache_key = (event.pk, layout.pk)
    if cache_key in _renderer_cache:
        cached_version, renderer = _renderer_cache[cache_key]
        if cached_version == version:
            return renderer

    bgf = _open_layout_background(layout)
    renderer = BadgeRenderer(
        event,
        layout.layout_data,
        bgf,
        ask_user_fields=(layout.ask_user_fields_data if layout.allow_customization else []),
    )
    _renderer_cache[cache_key] = (version, renderer)
    return renderer


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
                    pagesizes.portrait(pagesizes.A4)[1] / 2,
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
                    pagesizes.landscape(pagesizes.A4)[1] / 2,
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


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _fit_badge_to_slot(page, slot_width, slot_height):
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)
    if page_width <= 0 or page_height <= 0:
        return None

    scale = min(slot_width / page_width, slot_height / page_height)
    offset_x = (slot_width - page_width * scale) / 2
    offset_y = (slot_height - page_height * scale) / 2
    writer = PdfWriter()
    fitted = writer.add_blank_page(
        width=Decimal('%.5f' % slot_width),
        height=Decimal('%.5f' % slot_height),
    )
    fitted.merge_transformed_page(
        page,
        Transformation().scale(scale, scale).translate(offset_x, offset_y),
        expand=False,
    )
    return fitted


def render_nup_page(nup_pdf: PdfWriter, input_pages, opt: dict):
    badges_per_page = opt['cols'] * opt['rows']
    slot_width = float(opt['offsets'][0])
    slot_height = float(opt['offsets'][1])
    nup_page = nup_pdf.add_blank_page(
        width=Decimal('%.5f' % (opt['pagesize'][0])),
        height=Decimal('%.5f' % (opt['pagesize'][1])),
    )
    for i, page in enumerate(input_pages):
        slot = i % badges_per_page
        tx = float(opt['margins'][3] + (slot % opt['cols']) * opt['offsets'][0])
        ty = float(opt['margins'][2] + (opt['rows'] - 1 - (slot // opt['cols'])) * opt['offsets'][1])
        fitted = _fit_badge_to_slot(page, slot_width, slot_height)
        if fitted is None:
            continue
        nup_page.merge_transformed_page(
            fitted,
            Transformation().translate(tx, ty),
            expand=False,
        )
    return nup_page


def merge_pages(file_paths: list[str], output_file: BinaryIO):
    merger = PdfWriter()
    merger.add_metadata(
        {
            '/Title': 'Badges',
            '/Creator': 'eventyay',
        }
    )
    for pdf in file_paths:
        merger.append(pdf)
    merger.write(output_file)


def render_nup(input_files: list[str], num_pages: int, output_file: BinaryIO, opt: dict):
    badges_per_page = opt['cols'] * opt['rows']
    max_nup_pages = 20
    nup_pdf_files = []
    temp_dir = None
    if num_pages > badges_per_page * max_nup_pages:
        try:
            temp_dir = tempfile.TemporaryDirectory()
        except OSError:
            pass

    try:
        badges_pdf = PdfReader(input_files.pop(0))
        offset = 0
        for i, chunk_indices in enumerate(chunks(list(range(num_pages)), badges_per_page * max_nup_pages)):
            chunk = []
            for j in chunk_indices:
                if j - offset >= len(badges_pdf.pages):
                    offset += len(badges_pdf.pages)
                    badges_pdf = PdfReader(input_files.pop(0))
                chunk.append(badges_pdf.pages[j - offset])

            nup_pdf = PdfWriter()
            nup_pdf.add_metadata(
                {
                    '/Title': 'Badges',
                    '/Creator': 'eventyay',
                }
            )

            for page_chunk in chunks(chunk, badges_per_page):
                render_nup_page(nup_pdf, page_chunk, opt)

            if temp_dir:
                file_path = os.path.join(temp_dir.name, f'badges-{i}.pdf')
                nup_pdf.write(file_path)
                nup_pdf_files.append(file_path)
            else:
                nup_pdf.write(output_file)
                return

        if temp_dir:
            merge_pages(nup_pdf_files, output_file)
    finally:
        if temp_dir:
            try:
                temp_dir.cleanup()
            except OSError:
                pass


def render_badges(event, positions, opt, apply_output_pagesize=False):
    from itertools import groupby

    # Fetched once per render call (not per position) to avoid a cache round-trip per
    # badge, while still guaranteeing that every render reflects the latest saved design.
    version = get_badge_layout_version(event)

    op_renderers = []
    for op in positions:
        layout = get_badge_layout_for_position(event, op)
        if layout is not None:
            renderer = _renderer(event, layout, version)
            if renderer:
                op_renderers.append((op, renderer))

    if not op_renderers:
        raise OrderError(_('None of the selected products is configured to print badges.'))

    badge_pdf = PdfWriter()
    badge_pdf.add_metadata(
        {
            '/Title': 'Badges',
            '/Creator': 'eventyay',
        }
    )

    # Group consecutive badges by renderer to minimize Canvas and PdfReader overhead
    for renderer, group in groupby(op_renderers, key=lambda x: x[1]):
        ops = [x[0] for x in group]
        buffer = BytesIO()
        page = canvas.Canvas(buffer, pagesize=pagesizes.A4)

        for op in ops:
            with language(op.order.locale, op.order.event.settings.region):
                renderer.draw_page(page, op.order, op, show_page=False)
            if apply_output_pagesize and opt['pagesize']:
                page.setPageSize(opt['pagesize'])
            page.showPage()

        page.save()
        for merged_page in renderer.merge_foreground_buffer(buffer):
            badge_pdf.add_page(merged_page)

    return badge_pdf, len(badge_pdf.pages)


def render_pdf(event, positions, opt):
    Renderer._register_fonts()
    badges_per_page = opt['cols'] * opt['rows']
    outbuffer = BytesIO()

    if badges_per_page == 1:
        badge_pdf, _ = render_badges(event, positions, opt, apply_output_pagesize=True)
        badge_pdf.write(outbuffer)
    else:
        with tempfile.TemporaryDirectory() as tmp_dir:
            page_pdfs = []
            total_num_pages = 0
            for position_chunk in chunks(list(positions), 200):
                badge_pdf, num_pages = render_badges(event, position_chunk, opt)
                out_pdf_name = os.path.join(tmp_dir, f'chunk-{len(page_pdfs)}.pdf')
                with open(out_pdf_name, 'wb') as out_pdf:
                    badge_pdf.write(out_pdf)
                page_pdfs.append(out_pdf_name)
                total_num_pages += num_pages
                del badge_pdf

            render_nup(page_pdfs, total_num_pages, outbuffer, opt)

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
                        queryset=exclude_explicit_no_badge(self.event.products, BadgeProduct, 'product'),
                        label=_('Limit to products'),
                        widget=searchable_scrolling_checkbox_widget(),
                        initial=self.event.products.filter(admission=True),
                    ),
                ),
                (
                    'vouchers',
                    forms.ModelMultipleChoiceField(
                        queryset=exclude_explicit_no_badge(
                            self.event.vouchers.order_by('code'),
                            BadgeVoucher,
                            'voucher',
                        ),
                        label=_('Limit to vouchers'),
                        required=False,
                        widget=searchable_scrolling_checkbox_widget(),
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
                                    f'name:{k}',
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

    def render(self, form_data: dict) -> tuple[str, str, str]:
        qs = (
            OrderPosition.objects.filter(order__event=self.event, product_id__in=form_data['products'])
            .prefetch_related('answers', 'answers__question', 'answers__options')
            .select_related('order', 'order__invoice_address', 'product', 'variation', 'addon_to', 'subevent', 'seat', 'voucher')
        )

        if form_data.get('vouchers'):
            qs = qs.filter(voucher_id__in=form_data['vouchers'])

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
