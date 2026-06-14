import logging
from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView

from eventyay.base.import_utils import setting_is_truthy
from eventyay.base.models import CachedFile
from eventyay.base.orderimport import get_product_import_preview
from eventyay.base.services.locking import LockTimeoutException
from eventyay.base.services.orderimport import import_orders, parse_csv
from eventyay.base.views.tasks import AsyncAction
from eventyay.consts import SizeKey
from eventyay.control.forms.orderimport import ProcessForm
from eventyay.control.permissions import EventPermissionRequiredMixin

logger = logging.getLogger(__name__)


def import_settings_from_form(form):
    import_settings = {}
    for name in form.fields:
        if form.is_bound and getattr(form, 'cleaned_data', None) and name in form.cleaned_data:
            import_settings[name] = form.cleaned_data[name]
        elif form.is_bound:
            import_settings[name] = form.data.get(name)
        else:
            import_settings[name] = form[name].value()
    if 'create_missing_products' not in import_settings or import_settings['create_missing_products'] is None:
        if form.is_bound and getattr(form, 'cleaned_data', None) and 'create_missing_products' in form.cleaned_data:
            import_settings['create_missing_products'] = form.cleaned_data['create_missing_products']
        elif form.is_bound:
            import_settings['create_missing_products'] = setting_is_truthy(form.data.get('create_missing_products'))
        else:
            import_settings['create_missing_products'] = setting_is_truthy(
                form.initial.get('create_missing_products')
            )
    return import_settings


class ImportView(EventPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/orders/import_start.html'
    permission = 'can_change_orders'

    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            return redirect(
                reverse(
                    'control:event.orders.import',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.organizer.slug,
                    },
                )
            )
        if not request.FILES['file'].name.lower().endswith('.csv'):
            messages.error(request, _('Please only upload CSV files.'))
            return redirect(
                reverse(
                    'control:event.orders.import',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.organizer.slug,
                    },
                )
            )
        if request.FILES['file'].size > settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_OTHER]:
            max_size_bytes = settings.MAX_SIZE_CONFIG["other"]
            max_size_mb = max_size_bytes / (1024 * 1024)
            messages.error(
                request,
                _('Please do not upload files larger than {size:.0f} MB.').format(
                    size=max_size_mb
                ),
            )
            return redirect(
                reverse(
                    'control:event.orders.import',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.organizer.slug,
                    },
                )
            )

        cf = CachedFile.objects.create(
            expires=now() + timedelta(days=1),
            date=now(),
            filename='import.csv',
            type='text/csv',
        )
        cf.file.save('import.csv', request.FILES['file'])
        return redirect(
            reverse(
                'control:event.orders.import.process',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.organizer.slug,
                    'file': cf.id,
                },
            )
        )


class ProcessView(EventPermissionRequiredMixin, AsyncAction, FormView):
    permission = 'can_change_orders'
    template_name = 'pretixcontrol/orders/import_process.html'
    form_class = ProcessForm
    task = import_orders
    known_errortypes = ['DataImportError', 'LockTimeoutException']

    def get_error_message(self, exception):
        if isinstance(exception, LockTimeoutException) or (
            isinstance(exception, dict) and exception.get('exc_type') == 'LockTimeoutException'
        ):
            return _(
                'We were not able to complete the import because the event is busy. '
                'Please try again in a moment.'
            )
        return super().get_error_message(exception)

    def get_form_kwargs(self):
        k = super().get_form_kwargs()
        k.update(
            {
                'event': self.request.event,
                'initial': self.request.event.settings.order_import_settings,
                'headers': self.parsed.fieldnames if self.parsed else [],
            }
        )
        return k

    def form_valid(self, form):
        import_settings = dict(form.cleaned_data)
        self.request.event.settings.order_import_settings = import_settings
        return self.do(
            self.request.event.pk,
            self.file.id,
            import_settings,
            self.request.LANGUAGE_CODE,
            self.request.user.pk,
        )

    @cached_property
    def file(self):
        return get_object_or_404(CachedFile, pk=self.kwargs.get('file'), filename='import.csv')

    @cached_property
    def _parsed_csv(self):
        upload = self.file.file
        upload.open('rb')
        try:
            upload.seek(0)
            reader = parse_csv(upload, settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])
            if not reader:
                return None, [], 0, {}
            fieldnames = reader.fieldnames
            sample_rows = []
            record_count = 0
            csv_value_counts = {f'csv:{header}': defaultdict(int) for header in fieldnames}
            for row in reader:
                record_count += 1
                if len(sample_rows) < 3:
                    sample_rows.append(row)
                for header in fieldnames:
                    val = row.get(header)
                    if val:
                        csv_value_counts[f'csv:{header}'][str(val)] += 1
            return fieldnames, sample_rows, record_count, csv_value_counts
        finally:
            upload.close()

    @property
    def parsed(self):
        fieldnames, _sample, _count, _counts = self._parsed_csv
        if fieldnames is None:
            return None
        return SimpleNamespace(fieldnames=fieldnames)

    @cached_property
    def parsed_records(self):
        _fieldnames, sample_rows, _count, _counts = self._parsed_csv
        return sample_rows

    @cached_property
    def csv_record_count(self):
        _fieldnames, _sample, record_count, _counts = self._parsed_csv
        return record_count

    @cached_property
    def csv_product_value_counts(self):
        _fieldnames, _sample, _count, csv_value_counts = self._parsed_csv
        return csv_value_counts

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        return FormView.get(self, request, *args, **kwargs)

    def get_success_message(self, value):
        return _('The import was successful.')

    def get_success_url(self, value):
        return reverse(
            'control:event.orders',
            kwargs={
                'event': self.request.event.slug,
                'organizer': self.request.organizer.slug,
            },
        )

    def dispatch(self, request, *args, **kwargs):
        # When we're just polling the Celery result, the CachedFile may already
        # have been deleted by the task (cf.delete() is its last step).  Skip
        # the file/parse check so we don't raise a 404 before get_result() can
        # return the success redirect to the browser.
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return super().dispatch(request, *args, **kwargs)
        if not self.parsed:
            messages.error(
                request,
                _("We've been unable to parse the uploaded file as a CSV file."),
            )
            return redirect(
                reverse(
                    'control:event.orders.import',
                    kwargs={
                        'event': request.event.slug,
                        'organizer': request.organizer.slug,
                    },
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_error_url(self):
        return reverse(
            'control:event.orders.import.process',
            kwargs={
                'event': self.request.event.slug,
                'organizer': self.request.organizer.slug,
                'file': self.file.id,
            },
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = kwargs.get('form') or self.get_form()
        parsed = self.parsed
        parsed_records = self.parsed_records
        import_settings = import_settings_from_form(form)
        product_preview = get_product_import_preview(
            self.request.event,
            import_settings,
            fieldnames=parsed.fieldnames if parsed else [],
            csv_value_counts=self.csv_product_value_counts if parsed else None,
            record_count=self.csv_record_count if parsed else None,
        )
        ctx['file'] = self.file
        ctx['parsed'] = parsed
        ctx['sample_rows'] = parsed_records
        ctx['product_preview'] = product_preview
        active_products = self.request.event.products.filter(active=True)
        ctx['product_preview_labels'] = {
            'record_count': self.csv_record_count if parsed else 0,
            'unmapped_warning': str(
                _(
                    'Select a CSV column or existing product for the Product field in the column mapping '
                    'section below to preview which products will be matched or created.'
                )
            ),
            'summary_text': str(
                _(
                    'This summary is based on all rows in your CSV file. It updates when you change the '
                    'product mapping or the “Automatically create missing products” option.'
                )
            ),
            'static_products': {str(p.pk): str(p) for p in active_products},
            'matched_heading': str(_('Existing products (will be matched)')),
            'create_heading': str(_('New products (will be created)')),
            'missing_heading': str(_('Unknown products (import will fail)')),
            'ambiguous_heading': str(_('Ambiguous matches (import will fail)')),
            'col_csv_value': str(_('Value in CSV')),
            'col_matched_product': str(_('Matched product')),
            'col_result': str(_('Result')),
            'col_rows': str(_('Rows')),
            'col_matching_products': str(_('Matching products')),
            'result_will_create': str(_('Will be created')),
            'result_no_match': str(_('No matching product')),
            'empty_values': str(_('No product values found in the selected column.')),
        }
        return ctx
