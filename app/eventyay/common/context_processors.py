import logging
import sys
import warnings
from collections import Counter
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpRequest
from django.urls import resolve
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django_scopes import get_scope

from eventyay.base.models.settings import GlobalSettings
from eventyay.cfp.signals import footer_link, html_head
from eventyay.helpers.formats.variants import get_day_month_date_format
from eventyay.helpers.i18n import get_javascript_format, get_moment_locale, is_rtl

from .text.phrases import phrases

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _get_native_language_name(code: str) -> str:
    language_info = settings.LANGUAGES_INFORMATION.get(code, {})
    language_name = language_info.get('name')
    if language_name is None:
        return code
    with translation.override(code):
        return str(language_name)


def add_events(request: HttpRequest):
    if (
        request.resolver_match
        and set(request.resolver_match.namespaces) & {'orga', 'plugins'}
        and not request.user.is_anonymous
    ):
        try:
            url = resolve(request.path_info)
            url_name = url.url_name
            url_namespace = url.namespace
        except Http404:  # pragma: no cover
            url_name = ''
            url_namespace = ''
        return {'url_name': url_name, 'url_namespace': url_namespace}
    return {}


def locale_context(request):
    cal_static_dir = Path(__file__).parent.parent.joinpath('static', 'vendored', 'fullcalendar', 'locales')
    AVAILABLE_CALENDAR_LOCALES = tuple(
        f.name.removesuffix('.global.min.js') for f in cal_static_dir.rglob('*.global.min.js')
    )
    supported_languages = [
        (code, settings.LANGUAGES_INFORMATION[code]['natural_name']) for code in dict(settings.LANGUAGES)
    ]
    natural_name_counts = Counter(natural_name for __, natural_name in supported_languages)
    labels_by_code = {}
    for code, natural_name in supported_languages:
        label = natural_name
        if natural_name_counts[natural_name] > 1:
            native_language_name = _get_native_language_name(code)
            if native_language_name:
                label = native_language_name
        labels_by_code[code] = label

    # Ensure labels remain unique even if native variants still collide.
    label_counts = Counter(labels_by_code.values())
    languages_with_natural_names = []
    for code, __ in supported_languages:
        label = labels_by_code[code]
        if label_counts[label] > 1:
            label = f'{label} ({code})'
        languages_with_natural_names.append((code, label))
    languages = sorted(
        languages_with_natural_names,
        key=lambda l: (
            0 if l[0] in settings.LANGUAGES_OFFICIAL else (1 if l[0] not in settings.LANGUAGES_INCUBATING else 2),
            str(l[1]),
        ),
    )
    language_options = [{'code': code, 'label': name} for code, name in languages]

    context = {
        'js_date_format': get_javascript_format('DATE_INPUT_FORMATS'),
        'js_datetime_format': get_javascript_format('DATETIME_INPUT_FORMATS'),
        'js_locale': get_moment_locale(),
        'quotation_open': phrases.base.quotation_open,
        'quotation_close': phrases.base.quotation_close,
        'DAY_MONTH_DATE_FORMAT': get_day_month_date_format(),
        'rtl': is_rtl(getattr(request, 'LANGUAGE_CODE', 'en')),
        'AVAILABLE_CALENDAR_LOCALES': AVAILABLE_CALENDAR_LOCALES,
        'language_options': language_options,
    }

    lang = translation.get_language()
    try:
        lang_info = translation.get_language_info(lang)
        context['html_locale'] = lang_info.get('public_code', lang)
    except KeyError:
        context['html_locale'] = lang
    return context


def messages(request):
    return {'phrases': phrases}


def system_information(request):
    context = {
        'INSTANCE_NAME': settings.INSTANCE_NAME,
    }
    _footer = []
    _head = []
    event = getattr(request, 'event', None)

    if not request.path.startswith('/orga/'):
        context['footer_links'] = []
        context['header_links'] = []

        if event and get_scope():
            context['footer_links'] = [
                {'label': link.label, 'url': link.url} for link in event.extra_links.all() if link.role == 'footer'
            ]
            context['header_links'] = [
                {'label': link.label, 'url': link.url} for link in event.extra_links.all() if link.role == 'header'
            ]
            context['show_online_video_link'] = bool(event.settings.venueless_url) and event.settings.get('venueless_show_public_link', False)
        for __, response in footer_link.send(event, request=request):
            if isinstance(response, list):
                _footer += response
            else:  # pragma: no cover
                _footer.append(response)
                warnings.warn(
                    'Please return a list in your footer_link signal receiver, not a dictionary.',
                    DeprecationWarning,
                )
        context['footer_links'] += _footer

        if event and get_scope():
            for _receiver, response in html_head.send(event, request=request):
                _head.append(response)
            context['html_head'] = ''.join(_head)

    if settings.DEBUG:
        context['development_mode'] = True
        context['eventyay_version'] = settings.EVENTYAY_VERSION

    context['warning_update_available'] = False
    context['warning_update_check_active'] = False
    context['base_path'] = settings.BASE_PATH
    if not request.user.is_anonymous and request.user.is_administrator and request.path.startswith('/orga'):
        gs = GlobalSettings()
        if gs.settings.update_check_result_warning:
            context['warning_update_available'] = True
        if not gs.settings.update_check_ack and 'runserver' not in sys.argv:
            context['warning_update_check_active'] = True
    return context
