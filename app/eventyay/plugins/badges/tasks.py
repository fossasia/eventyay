import logging

from django.core.files.base import ContentFile

from eventyay.base.models import (
    CachedFile,
    Event,
    OrderPosition,
    cachedfile_name,
)
from eventyay.base.services.orders import OrderError
from eventyay.base.services.tasks import EventTask
from eventyay.celery_app import app

from .exporters import OPTIONS, render_pdf


logger = logging.getLogger(__name__)


@app.task(base=EventTask, throws=(OrderError,))
def badges_create_pdf(event: Event, fileid: int, positions: list[int]) -> int:
    file = CachedFile.objects.get(id=fileid)

    qs = (
        OrderPosition.objects.filter(id__in=positions)
        .select_related(
            'order', 'order__event', 'order__invoice_address', 'product', 'variation', 'addon_to', 'subevent', 'seat', 'voucher'
        )
        .prefetch_related('answers', 'answers__question', 'answers__options')
    )

    pdfcontent = render_pdf(event, qs, opt=OPTIONS['one'])
    file.file.save(cachedfile_name(file, file.filename), ContentFile(pdfcontent.read()))
    file.save()
    return file.pk
