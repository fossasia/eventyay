import logging

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils import translation
from django.utils.translation import get_language_info
from django_scopes import get_scope
from i18nfield.strings import LazyI18nString

from eventyay.base.models.page import Page
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.permissions import is_event_organiser, user_has_cfp_submissions
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

        if not request.event.settings.get('presale_css_file'):
            lock_key = f'presale:regenerate_css:{request.event.pk}'
            if cache.add(lock_key, True, 60):
                try:
                    from eventyay.presale.style import regenerate_css

                    regenerate_css.apply_async(args=(request.event.pk,))
                except Exception:
                    cache.delete(lock_key)
                    logger.warning(
                        'Could not enqueue presale CSS regeneration for %s/%s',
                        request.event.organizer.slug,
                        request.event.slug,
                        exc_info=True,
                    )

        if request.event.settings.presale_css_file:
            ctx['css_file'] = default_storage.url(request.event.settings.presale_css_file)

        ctx['current_event_font'] = request.event.settings.get('primary_font', default='')

        ctx['event_logo'] = request.event.visible_header_image_url or ''
        ctx['event_logo_image'] = request.event.visible_logo_url or ''
        try:
            ctx['social_image'] = request.event.cache.get_or_set('social_image_url', request.event.social_image, 60)
        except (ValueError, OSError) as e:
            logger.error('Could not generate social image. Error: %s', e)

        ctx['event'] = request.event
        ctx['languages'] = [_safe_language_info(code) for code in request.event.settings.locales]

        if request.resolver_match:
            ctx['cart_namespace'] = request.resolver_match.kwargs.get('cart_namespace', '')
    elif hasattr(request, 'organizer'):
        if not request.organizer.settings.get('presale_css_file') and not hasattr(request, 'event'):
            lock_key = f'presale:regenerate_organizer_css:{request.organizer.pk}'
            if cache.add(lock_key, True, 60):
                try:
                    from eventyay.presale.style import regenerate_organizer_css

                    regenerate_organizer_css.apply_async(args=(request.organizer.pk,))
                except Exception:
                    cache.delete(lock_key)
                    logger.warning(
                        'Could not enqueue presale CSS regeneration for %s',
                        request.organizer.slug,
                        exc_info=True,
                    )
        ctx['languages'] = [_safe_language_info(code) for code in request.organizer.settings.locales]
        if request.organizer.settings.presale_css_file and not hasattr(request, 'event'):
            ctx['css_file'] = default_storage.url(request.organizer.settings.presale_css_file)

        ctx['organizer_homepage_text'] = request.organizer.settings.get(
            'organizer_homepage_text', as_type=LazyI18nString
        )
        ctx['organizer'] = request.organizer

    if hasattr(request, 'organizer'):
        logo_path = request.organizer.settings.get('organizer_logo_image', as_type=str, default='')
        ctx['organizer_logo'] = logo_path[7:] if logo_path.startswith('file://') else logo_path
        ctx['organizer_logo_url'] = default_storage.url(ctx['organizer_logo']) if ctx['organizer_logo'] else None

        header_path = request.organizer.settings.get('organizer_header_image', as_type=str, default='')
        ctx['organizer_header'] = header_path[7:] if header_path.startswith('file://') else header_path
        ctx['organizer_header_url'] = default_storage.url(ctx['organizer_header']) if ctx['organizer_header'] else None

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
        ctx['html_locale'] = translation.get_language_info(lang).get('public_code', translation.get_language())
    except KeyError:
        ctx['html_locale'] = translation.get_language()
    ctx['settings'] = eventyay_settings
    global_settings = GlobalSettingsObject().settings
    ctx['global_settings'] = {
        'leaflet_tiles': global_settings.get('leaflet_tiles'),
        'leaflet_tiles_attribution': global_settings.get('leaflet_tiles_attribution'),
    }
    ctx['django_settings'] = settings

    # Check to show organizer area (only for team members or admins)
    ctx['show_organizer_area'] = False
    ctx['user_has_cfp_submissions'] = False
    ctx['talks_published'] = False
    if request.user and request.user.is_authenticated and hasattr(request, 'event') and request.event:
        ctx['show_organizer_area'] = is_event_organiser(request.user, request, request.event)
        ctx['talks_published'] = request.event.talks_published
        if ctx['talks_published']:
            ctx['user_has_cfp_submissions'] = user_has_cfp_submissions(request, request.event)

    ctx['show_link_in_header_for_all_pages'] = Page.objects.filter(link_in_system=True, link_in_header=True)
    ctx['show_link_in_footer_for_all_pages'] = Page.objects.filter(link_in_system=True, link_in_footer=True)

    return ctx
