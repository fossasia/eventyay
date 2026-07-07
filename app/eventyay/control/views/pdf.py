import json
import logging
import mimetypes
from datetime import timedelta
from io import BytesIO
from json import JSONDecodeError

from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext as _
from django.views.generic import TemplateView
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib.units import mm

from eventyay.base.i18n import language
from eventyay.base.models import CachedFile, InvoiceAddress, OrderPosition
from eventyay.base.pdf import get_images, get_variables
from eventyay.base.settings import PERSON_NAME_SCHEMES
from eventyay.consts import SizeKey
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.helpers.database import rolledback_transaction
from eventyay.presale.style import get_fonts

logger = logging.getLogger(__name__)

_INVALID_PAGE_SIZE_ERROR = _('Invalid height/width given.')
_BACKGROUND_PDF_READ_ERROR = _('Could not read the background PDF.')


def open_stored_pdf_file(file_field, *, default_path):
    from django.contrib.staticfiles import finders

    if isinstance(file_field, File) and file_field.name:
        return default_storage.open(file_field.name, 'rb')
    path = finders.find(default_path)
    if not path:
        raise FileNotFoundError(f'Static PDF not found: {default_path}')
    return open(path, 'rb')


class BaseEditorView(EventPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/pdf/index.html'
    permission = 'can_change_settings'
    accepted_formats = ('application/pdf',)
    maxfilesize = settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_PDF]
    minfilesize = 10
    title = None

    def get(self, request, *args, **kwargs):
        resp = super().get(request, *args, **kwargs)
        resp._csp_ignore = True
        return resp

    def process_upload(self):
        f = self.request.FILES.get('background')
        error = False
        if f.size > self.maxfilesize:
            error = _('The uploaded PDF file is too large.')
        if f.size < self.minfilesize:
            error = _('The uploaded PDF file is too small.')
        if mimetypes.guess_type(f.name)[0] not in self.accepted_formats:
            error = _('Please only upload PDF files.')
        # if there was an error, add error message to response_data and return
        if error:
            return error, None
        return None, f

    def _get_preview_position(self):
        product = self.request.event.products.create(
            name=_('Sample product'),
            default_price=42.23,
            description=_('Sample product description'),
        )
        product2 = self.request.event.products.create(name=_('Sample workshop'), default_price=23.40)

        from eventyay.base.models import Order

        order = self.request.event.orders.create(
            status=Order.STATUS_PENDING,
            datetime=now(),
            email='sample@eventyay.com',
            locale=self.request.event.settings.locale,
            expires=now(),
            code='PREVIEW1234',
            total=119,
        )

        scheme = PERSON_NAME_SCHEMES[self.request.event.settings.name_scheme]
        sample = {k: str(v) for k, v in scheme['sample'].items()}
        p = order.positions.create(product=product, attendee_name_parts=sample, price=product.default_price)
        order.positions.create(product=product2, attendee_name_parts=sample, price=product.default_price, addon_to=p)
        order.positions.create(product=product2, attendee_name_parts=sample, price=product.default_price, addon_to=p)

        InvoiceAddress.objects.create(order=order, name_parts=sample, company=_('Sample company'))
        return p

    def generate(self, p: OrderPosition, override_layout=None, override_background=None):
        raise NotImplementedError()

    def get_layout_settings_key(self):
        raise NotImplementedError()

    def get_background_settings_key(self):
        raise NotImplementedError()

    def get_default_background(self):
        raise NotImplementedError()

    def get_current_background(self):
        return (
            self.request.event.settings.get(self.get_background_settings_key()).url
            if self.request.event.settings.get(self.get_background_settings_key())
            else self.get_default_background()
        )

    def _normalize_layout(self, layout):
        for obj in layout or []:
            if isinstance(obj, dict) and obj.get('type') in ('text', 'textarea') and obj.get('content') == 'item':
                obj['content'] = 'event_name'
        return layout

    def _get_posted_layout(self):
        data = self.request.POST.get('data')
        if data is None or not data.strip():
            raise ValueError(_('No layout data was provided.'))

        try:
            layout = json.loads(data)
        except JSONDecodeError as exc:
            raise ValueError(_('Invalid layout data was provided.')) from exc

        if not isinstance(layout, list):
            raise ValueError(_('Invalid layout data was provided.'))

        return self._normalize_layout(layout)

    def _get_posted_layout_json(self):
        layout = self._get_posted_layout()
        return json.dumps(layout)

    def get_current_layout(self):
        return self._normalize_layout(self.request.event.settings.get(self.get_layout_settings_key(), as_type=list))

    def save_layout(self, layout_data=None):
        if layout_data is None:
            layout_data = self._get_posted_layout_json()
        self.request.event.settings.set(self.get_layout_settings_key(), layout_data)

    def save_background(self, f: CachedFile):
        fexisting = self.request.event.settings.get(self.get_background_settings_key(), as_type=File)
        if fexisting:
            try:
                default_storage.delete(fexisting.name)
            except OSError:  # pragma: no cover
                logger.error('Deleting file %s failed.', fexisting.name)

        # Create new file
        nonce = get_random_string(length=8)
        fname = 'pub/%s-%s/%s/%s.%s.%s' % (
            'event',
            'settings',
            self.request.event.pk,
            self.get_layout_settings_key(),
            nonce,
            'pdf',
        )
        newname = default_storage.save(fname, f.file)
        self.request.event.settings.set(self.get_background_settings_key(), 'file://' + newname)

    def _open_saved_background_pdf(self):
        raise NotImplementedError()

    def open_background_pdf(self, cached_file=None):
        if cached_file is not None and cached_file.file:
            return cached_file.file.open('rb')
        return self._open_saved_background_pdf()

    def _get_posted_cached_file(self):
        background_id = self.request.POST.get('background', '').strip()
        if not background_id:
            return None
        try:
            return CachedFile.objects.get(id=background_id)
        except CachedFile.DoesNotExist:
            return None

    def _parse_page_size_mm(self):
        try:
            width_mm = float(self.request.POST.get('width'))
            height_mm = float(self.request.POST.get('height'))
        except (TypeError, ValueError):
            return None, JsonResponse({'status': 'error', 'error': _INVALID_PAGE_SIZE_ERROR})
        if width_mm <= 0 or height_mm <= 0:
            return None, JsonResponse({'status': 'error', 'error': _INVALID_PAGE_SIZE_ERROR})
        return (width_mm, height_mm), None

    def _cached_file_json_response(self, cached_file):
        return JsonResponse(
            {
                'status': 'ok',
                'id': cached_file.id,
                'url': reverse(
                    'control:pdf.background',
                    kwargs={
                        'event': self.request.event.slug,
                        'organizer': self.request.organizer.slug,
                        'filename': str(cached_file.id),
                    },
                ),
            }
        )

    def _make_preview_cached_file(self):
        c = CachedFile(web_download=True)
        c.expires = now() + timedelta(days=7)
        c.date = now()
        c.filename = 'background_preview.pdf'
        c.type = 'application/pdf'
        c.save()
        return c

    def _background_cached_response(self, buffer, *, save_name='background.pdf'):
        c = self._make_preview_cached_file()
        c.file.save(save_name, ContentFile(buffer.read()))
        c.refresh_from_db()
        return self._cached_file_json_response(c)

    def _resize_background_pdf(self, width_mm, height_mm, cached_file=None):
        try:
            bg_file = self.open_background_pdf(cached_file)
        except NotImplementedError:
            return None, JsonResponse({'status': 'error', 'error': _('No background PDF available to resize.')})

        try:
            try:
                reader = PdfReader(BytesIO(bg_file.read()))
            finally:
                bg_file.close()

            page = reader.pages[0]
        except (PdfReadError, IndexError):
            logger.exception('Failed to read background PDF for resize')
            return None, JsonResponse({'status': 'error', 'error': _BACKGROUND_PDF_READ_ERROR})

        page.scale_to(width_mm * mm, height_mm * mm)
        writer = PdfWriter()
        writer.add_page(page)
        buffer = BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        return buffer, None

    def post(self, request, *args, **kwargs):
        if 'resizebackground' in request.POST:
            page_size, error_response = self._parse_page_size_mm()
            if error_response:
                return error_response

            width_mm, height_mm = page_size
            buffer, error_response = self._resize_background_pdf(
                width_mm,
                height_mm,
                cached_file=self._get_posted_cached_file(),
            )
            if error_response:
                return error_response
            return self._background_cached_response(buffer)

        if 'emptybackground' in request.POST:
            page_size, error_response = self._parse_page_size_mm()
            if error_response:
                return error_response

            width_mm, height_mm = page_size
            writer = PdfWriter()
            writer.add_blank_page(width=width_mm * mm, height=height_mm * mm)
            buffer = BytesIO()
            writer.write(buffer)
            buffer.seek(0)
            return self._background_cached_response(buffer, save_name='empty.pdf')

        if 'background' in request.FILES:
            error, fileobj = self.process_upload()
            if error:
                return JsonResponse({'status': 'error', 'error': error})
            c = self._make_preview_cached_file()
            c.file = fileobj
            c.save()
            c.refresh_from_db()
            return self._cached_file_json_response(c)

        cf = self._get_posted_cached_file()

        layout = None
        layout_data = None
        if 'preview' in request.POST or 'data' in request.POST:
            try:
                layout = self._get_posted_layout()
            except ValueError as exc:
                if 'preview' in request.POST:
                    return HttpResponseBadRequest(str(exc))
                return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

            layout_data = json.dumps(layout)

        if 'preview' in request.POST:
            with (
                rolledback_transaction(),
                language(request.event.settings.locale, request.event.settings.region),
            ):
                p = self._get_preview_position()
                fname, mimet, data = self.generate(
                    p,
                    override_layout=layout,
                    override_background=cf.file if cf else None,
                )

            resp = HttpResponse(data, content_type=mimet)
            ftype = fname.split('.')[-1]
            resp['Content-Disposition'] = 'inline; filename="ticket-preview.{}"'.format(ftype)
            return resp
        elif 'data' in request.POST:
            if cf:
                self.save_background(cf)
            self.save_layout(layout_data)
            return JsonResponse({'status': 'ok'})
        return HttpResponseBadRequest()

    def get_variables(self):
        return get_variables(self.request.event)

    def get_images(self):
        return get_images(self.request.event)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['fonts'] = get_fonts()
        ctx['pdf'] = self.get_current_background()
        ctx['variables'] = self.get_variables()
        ctx['images'] = self.get_images()
        ctx['layout'] = json.dumps(self.get_current_layout())
        ctx['title'] = self.title
        ctx['locales'] = [p for p in settings.LANGUAGES if p[0] in self.request.event.settings.locales]
        return ctx


class FontsCSSView(TemplateView):
    content_type = 'text/css'
    template_name = 'pretixcontrol/pdf/webfonts.css'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['fonts'] = get_fonts()
        return ctx


class PdfView(TemplateView):
    def get(self, request, *args, **kwargs):
        cf = get_object_or_404(CachedFile, id=kwargs.get('filename'), filename='background_preview.pdf')
        resp = FileResponse(cf.file, content_type='application/pdf')
        resp['Content-Disposition'] = 'attachment; filename="{}"'.format(cf.filename)
        return resp
