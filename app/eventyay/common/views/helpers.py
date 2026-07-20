import logging

from django.conf import settings
from django.http import FileResponse, Http404

logger = logging.getLogger(__name__)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def get_static(request, path, content_type, organizer=None, event=None, **kwargs):  # pragma: no cover
    path = settings.BASE_DIR / 'static' / path
    if not path.exists():
        logger.warning("Static asset %s not found", path)
        raise Http404()
    logger.debug("Serving static asset %s", path)
    return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=False)
