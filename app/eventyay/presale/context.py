import logging

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils import translation
from django.utils.translation import get_language_info
from django_scopes import get_scope
from i18nfield.strings import LazyI18nString
from django.core.exceptions import ObjectDoesNotExist


from eventyay.base.models.page import Page
from eventyay.base.settings import GlobalSettingsObject
from eventyay.helpers.i18n import (
    get_javascript_format_without_seconds,
    get_moment_locale,
)

from ..base.i18n import get_language_without_region
from .signals import (
    footer_link,
    global_footer_link,
    global_html_footer,
    global_html_head,
    global_html_page_header,
    html_footer,
    html_head,
    html_page_header,
)

logger = logging.getLogger(__name__)


def contextprocessor(request):
    """
    Adds data to all template contexts
    """
    if not hasattr(request, '_eventyay_presale_default_context'):
        request._eventyay_presale_default_context = _default_context(request)
    return request._eventyay_presale_default_context


def _safe_language_info(code):
    try:
        return get_language_info(code)
    except KeyError:
        return {'code': code, 'name': code, 'bidi': False, 'name_local': code, 'public_code': code}


def _default_context(request):
    if request.path.startswith('/control'):
        return {}

    ctx = {
        'css_file': None,
        'DEBUG': settings.DEBUG,
    }

    _html_head = []
    _html_page_header = []
    _html_foot = []
    _footer = []

    if hasattr(request, 'event'):
        eventyay_settings = request.event.settings
    elif hasattr(request, 'organizer'):
        eventyay_settings = request.organizer.settings
    else:
        eventyay_settings = GlobalSettingsObject().settings

    text = eventyay_settings.get('footer_text', as_type=LazyI18nString)
    link = eventyay_settings.get('footer_link', as_type=LazyI18nString)

    if text:
        if link:
            _footer.append({'url': str(link), 'label': str(text)})
        else:
            ctx['footer_text'] = str(text)

    for receiver, response in global_html_page_header.send(None, request=request):
        _html_page_header.append(response)
    for receiver, response in global_html_head.send(None, request=request):
        _html_head.append(response)
    for receiver, response in global_html_footer.send(None, request=request):
        _html_foot.append(response)
    for receiver, response in global_footer_link.send(None, request=request):
        if isinstance(response, list):
            _footer += response
        else:
            _footer.append(response)

    if hasattr(request, 'event') and get_scope():
        for receiver, response in html_head.send(request.event, request=request):
            _html_head.append(response)
        for receiver, response in html_page_header.send(request.event, request=request):
            _html_page_header.append(response)
        for receiver, response in html_footer.send(request.event, request=request):
            _html_foot.append(response)
        for receiver, response in footer_link.send(request.event, request=request):
            if isinstance(response, list):
                _footer += response
            else:
                _footer.append(response)

        if request.event.settings.presale_css_file:
            ctx['css_file'] = default_storage.url(request.event.settings.presale_css_file)

        ctx['event'] = request.event
        ctx['languages'] = [_safe_language_info(code) for code in request.event.settings.locales]

    elif hasattr(request, 'organizer'):
        ctx['languages'] = [_safe_language_info(code) for code in request.organizer.settings.locales]

    if hasattr(request, 'organizer'):
        ctx['organizer'] = request.organizer

    ctx['base_path'] = settings.BASE_PATH
    ctx['html_head'] = ''.join(h for h in _html_head if h)
    ctx['html_foot'] = ''.join(h for h in _html_foot if h)
    ctx['html_page_header'] = ''.join(h for h in _html_page_header if h)
    ctx['footer'] = _footer
    ctx['site_url'] = settings.SITE_URL

    ctx['js_datetime_format'] = get_javascript_format_without_seconds('DATETIME_INPUT_FORMATS')
    ctx['js_date_format'] = get_javascript_format_without_seconds('DATE_INPUT_FORMATS')
    ctx['js_time_format'] = get_javascript_format_without_seconds('TIME_INPUT_FORMATS')
    ctx['js_locale'] = get_moment_locale()

    lang = get_language_without_region()
    try:
        ctx['html_locale'] = translation.get_language_info(lang).get(
            'public_code', translation.get_language()
        )
    except KeyError:
        ctx['html_locale'] = translation.get_language()

    ctx['settings'] = eventyay_settings
    ctx['django_settings'] = settings

    # ------------------------------------
    # Organizer area visibility
    # ------------------------------------
    ctx['show_organizer_area'] = False

    if (
        request.user
        and request.user.is_authenticated
        and hasattr(request, 'organizer')
        and request.organizer
        and hasattr(request, 'event')
        and request.event
    ):
        ctx['show_organizer_area'] = request.user.has_event_permission(
            request.organizer,
            request.event,
            'can_change_event_settings',
            request=request,
        )

    # ------------------------------------
    # CFP visibility logic
    # ------------------------------------
    ctx['has_submissions'] = False
    ctx['talk_component_published'] = False

    if (
        request.user
        and request.user.is_authenticated
        and hasattr(request, 'event')
        and request.event
    ):
        try:
            from eventyay.cfp.models import Submission

            ctx['has_submissions'] = Submission.objects.filter(
                event=request.event,
                speakers__user=request.user
            ).exists()
        except (ImportError, ObjectDoesNotExist):
            ctx['has_submissions'] = False

        try:
            cfp = request.event.cfp
            ctx['talk_component_published'] = bool(cfp.is_public)
        except (AttributeError, ObjectDoesNotExist):
            ctx['talk_component_published'] = False

    ctx['show_link_in_header_for_all_pages'] = Page.objects.filter(link_in_header=True)
    ctx['show_link_in_footer_for_all_pages'] = Page.objects.filter(link_in_footer=True)

    return ctx
