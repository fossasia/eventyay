from django.http import FileResponse, Http404, JsonResponse
from django.utils.timezone import now

from eventyay.base.models import CachedFile


def export_status(request, event_slug, job_id):
    """
    GET /orga/event/<event>/export/status/<job_id>/
    Polled by the browser. Derives status from CachedFile state:
      - file saved         → done
      - expires passed     → failed (worker crashed or never ran)
      - otherwise          → processing
    """
    try:
        cf = CachedFile.objects.get(pk=job_id)
    except CachedFile.DoesNotExist:
        raise Http404

    if cf.file:
        return JsonResponse({
            'status': 'done',
            'download_url': request.build_absolute_uri(
                f'/orga/event/{event_slug}/export/download/{job_id}/'
            ),
        })

    if cf.expires and cf.expires < now():
        return JsonResponse({
            'status': 'failed',
            'error': 'Export did not complete in time. Please try again.',
        })

    return JsonResponse({'status': 'processing'})


def export_download(request, event_slug, job_id):
    """
    GET /orga/event/<event>/export/download/<job_id>/
    Streams the finished CSV to the browser.
    """
    try:
        cf = CachedFile.objects.get(pk=job_id)
    except CachedFile.DoesNotExist:
        raise Http404

    if not cf.file:
        raise Http404('Export file is not ready yet.')

    filename = getattr(cf, 'filename', None) or f'export-{job_id}.csv'
    return FileResponse(
        cf.file.open('rb'),
        content_type='text/csv; charset=utf-8',
        as_attachment=True,
        filename=filename,
    )