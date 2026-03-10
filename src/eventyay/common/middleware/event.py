import logging
import traceback
import zoneinfo
from contextlib import suppress
from urllib.parse import quote, urljoin

import jwt
from django.conf import settings
from django.contrib.auth import login
from django.db.models import OuterRef, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, reverse
from django.urls import resolve
from django.utils import timezone, translation
from django.utils.translation.trans_real import language_code_re, parse_accept_lang_header
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.base.models import User
from eventyay.base.models import Schedule
from eventyay.common.utils.language import (
    get_event_enforce_ui_language_cookie_name,
    get_event_language_cookie_name,
    set_current_event_language,
    strict_match_language,
    validate_language,
)


logger = logging.getLogger(__name__)


def get_login_redirect(request):
    params = request.GET.copy()
    next_url = params.pop('next', None)
    next_url = next_url[0] if next_url else request.path
    params = request.GET.urlencode() if request.GET else ''
    params = f'?next={quote(next_url)}&{params}'
    # event = getattr(request, 'event', None)
    # if event:
    is_orga_path = request.path.startswith('/orga')
    event = getattr(request, 'event', None)
    if event and not is_orga_path: 
        url = event.urls.login
        return redirect(url.full() + params)
    return redirect(reverse('eventyay_common:auth.login') + params)


class EventPermissionMiddleware:
    UNAUTHENTICATED_ORGA_URLS = (
        'invitation.view',
        'auth',
        'login',
        'auth.reset',
        'auth.recover',
        'event.auth.reset',
        'event.auth.recover',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _handle_orga_url(self, request, url):
        if request.uses_custom_domain:
            return redirect(urljoin(settings.SITE_URL, request.get_full_path()))
        if request.user.is_anonymous and url.url_name not in self.UNAUTHENTICATED_ORGA_URLS:
            return get_login_redirect(request)
        return None

    def __call__(self, request):
        url = resolve(request.path_info)

        organizer_slug = url.kwargs.get('organizer')
        if organizer_slug:
            request.organizer = get_object_or_404(Organizer, slug__iexact=organizer_slug)

        event_slug = url.kwargs.get('event')
        if event_slug:
            with scopes_disabled():
                try:
                    queryset = Event.objects.prefetch_related('submissions', 'extra_links', 'schedules').select_related(
                        'organizer'
                    )
                    latest_schedule_subquery = (
                        Schedule.objects.filter(event=OuterRef('pk'), published__isnull=False)
                        .order_by('-published')
                        .values('pk')[:1]
                    )
                    queryset = queryset.annotate(_current_schedule_pk=Subquery(latest_schedule_subquery))
                    
                    # If organizer is in URL, ensure event belongs to that organizer
                    if organizer_slug:
                        request.event = queryset.filter(
                            slug__iexact=event_slug,
                            organizer__slug__iexact=organizer_slug
                        ).first()
                        if not request.event:
                            with suppress(ValueError, TypeError):
                                event_id = int(event_slug)
                                request.event = queryset.filter(
                                    pk=event_id,
                                    organizer__slug__iexact=organizer_slug
                                ).first()
                    else:
                        request.event = queryset.filter(slug__iexact=event_slug).first()
                        if not request.event:
                            with suppress(ValueError, TypeError):
                                event_id = int(event_slug)
                                request.event = queryset.filter(pk=event_id).first()
                    if not request.event:
                        raise Http404("No Event matches the given query.")
                except ValueError:
                    raise Http404()
        event = getattr(request, 'event', None)

        self._select_locale(request)
        is_exempt = url.url_name == 'export' if 'agenda' in url.namespaces else request.path.startswith('/api/')

        if 'orga' in url.namespaces or ('plugins' in url.namespaces and request.path.startswith('/orga')):
            response = self._handle_orga_url(request, url)
            if response:
                return response
        elif event and request.event.custom_domain and not request.uses_custom_domain and not is_exempt:
            response = redirect(urljoin(request.event.custom_domain, request.get_full_path()))
            response['Access-Control-Allow-Origin'] = '*'
            return response
        if event and not event.user_can_view_talks(request.user, request=request):
            if 'agenda' in url.namespaces or 'cfp' in url.namespaces:
                if url.url_name != 'event.css':
                    raise Http404()
        if event:
            with scope(event=event):
                response = self.get_response(request)
        else:
            response = self.get_response(request)

        if is_exempt and 'Access-Control-Allow-Origin' not in response:
            response['Access-Control-Allow-Origin'] = '*'
        return response

    def _select_locale(self, request):
        # Clear previous event language for this thread
        set_current_event_language(None)
        request.event_language_enforce_ui = False

        # UI language: use full platform languages and keep existing precedence
        ui_supported = list(settings.LANGUAGES_INFORMATION)
        ui_language = (
            self._language_from_request(request, ui_supported)
            or self._language_from_user(request, ui_supported)
            or self._language_from_cookie(request, ui_supported)
            or self._language_from_browser(request, ui_supported)
            or settings.LANGUAGE_CODE
        )
        translation.activate(ui_language)
        request.LANGUAGE_CODE = translation.get_language()
        request.ui_language = ui_language

        # Event content language: limited to event locales when available
        event_language = None
        if hasattr(request, 'event') and request.event:
            event_supported = request.event.locales
            enforce_cookie_name = get_event_enforce_ui_language_cookie_name(
                request.event.slug,
                request.event.organizer.slug,
            )
            request.event_language_enforce_ui = request.COOKIES.get(enforce_cookie_name, '0') == '1'

            if request.event_language_enforce_ui:
                strict_ui_language = strict_match_language(ui_language, event_supported)
                if strict_ui_language:
                    event_language = strict_ui_language

            cookie_name = get_event_language_cookie_name(request.event.slug, request.event.organizer.slug)
            if not event_language:
                event_language = self._language_from_cookie(request, event_supported, cookie_name)
            if not event_language:
                event_language = self._language_from_event(request, event_supported)
            if not event_language and event_supported:
                event_language = event_supported[0]

        if not event_language:
            event_language = ui_language

        request.event_language = event_language
        set_current_event_language(event_language)

        with suppress(zoneinfo.ZoneInfoNotFoundError):
            if hasattr(request, 'event') and request.event:
                tzname = request.event.timezone
            elif request.user.is_authenticated:
                tzname = request.user.timezone
            else:
                tzname = settings.TIME_ZONE
            timezone.activate(zoneinfo.ZoneInfo(tzname))
            request.timezone = tzname

    def _language_from_browser(self, request, supported):
        accept_value = request.headers.get('Accept-Language', '')
        for accept_lang, _ in parse_accept_lang_header(accept_value):
            if accept_lang == '*':
                break

            if not language_code_re.search(accept_lang):
                continue

            accept_lang = self._validate_language(accept_lang, supported)
            if accept_lang:
                return accept_lang

    def _language_from_cookie(self, request, supported, cookie_name=settings.LANGUAGE_COOKIE_NAME):
        cookie_value = request.COOKIES.get(cookie_name)
        return self._validate_language(cookie_value, supported)

    def _language_from_user(self, request, supported):
        if request.user.is_authenticated:
            return self._validate_language(request.user.locale, supported)

    def _language_from_request(self, request, supported):
        lang = request.GET.get('lang')
        if lang:
            lang = self._validate_language(lang, supported)
            if lang:
                request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = lang
                return lang

    def _language_from_event(self, request, supported):
        if hasattr(request, 'event') and request.event:
            return self._validate_language(request.event.locale, supported)

    @staticmethod
    def _validate_language(value, supported):
        return validate_language(value, supported)
