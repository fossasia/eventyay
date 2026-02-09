from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View

from eventyay.base.models.event import Event
from eventyay.common.utils.language import (
    get_event_enforce_ui_language_cookie_name,
    get_event_language_cookie_name,
    strict_match_language,
    validate_language,
)

from .robots import NoSearchIndexViewMixin


def _cookie_expires(max_age: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max_age)).strftime('%a, %d-%b-%Y %H:%M:%S GMT')


class LocaleSet(NoSearchIndexViewMixin, View):
    def get(self, request, *args, **kwargs):
        url = request.GET.get('next', request.headers.get('Referer', '/'))
        url = url if url_has_allowed_host_and_scheme(url, allowed_hosts=[request.get_host()]) else '/'
        resp = HttpResponseRedirect(url)

        locale = request.GET.get('locale')
        if locale in [lc for lc, ll in settings.LANGUAGES]:
            max_age = 10 * 365 * 24 * 60 * 60
            if request.user.is_authenticated and request.user.locale != locale:
                request.user.locale = locale
                request.user.save(update_fields=['locale'])
            resp.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                locale,
                max_age=max_age,
                expires=_cookie_expires(max_age),
                domain=settings.SESSION_COOKIE_DOMAIN,
            )

        return resp


class EventLocaleSet(NoSearchIndexViewMixin, View):
    def get(self, request, *args, **kwargs):
        url = request.GET.get('next', request.headers.get('Referer', '/'))
        url = url if url_has_allowed_host_and_scheme(url, allowed_hosts=[request.get_host()]) else '/'
        resp = HttpResponseRedirect(url)

        locale = request.GET.get('locale')
        enforce_ui_language = request.GET.get('enforce_ui_language')
        organizer_slug = request.GET.get('organizer')
        event_slug = request.GET.get('event')

        event = getattr(request, 'event', None)
        if not event and event_slug:
            event = (
                Event.objects.filter(slug=event_slug, organizer__slug=organizer_slug).first()
                if organizer_slug
                else Event.objects.filter(slug=event_slug).first()
            )

        if event:
            max_age = 10 * 365 * 24 * 60 * 60
            supported = event.locales
            event_cookie_name = get_event_language_cookie_name(event.slug, event.organizer.slug)
            enforce_cookie_name = get_event_enforce_ui_language_cookie_name(event.slug, event.organizer.slug)
            ui_language = getattr(request, 'ui_language', request.LANGUAGE_CODE or settings.LANGUAGE_CODE)
            strict_ui_language = strict_match_language(ui_language, supported)

            if enforce_ui_language is not None:
                enforce_enabled = enforce_ui_language == '1'
                resp.set_cookie(
                    enforce_cookie_name,
                    '1' if enforce_enabled else '0',
                    max_age=max_age,
                    expires=_cookie_expires(max_age),
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path='/',
                )

                if enforce_enabled and strict_ui_language:
                    resp.set_cookie(
                        event_cookie_name,
                        strict_ui_language,
                        max_age=max_age,
                        expires=_cookie_expires(max_age),
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path='/',
                    )
                elif not enforce_enabled and not locale and getattr(request, 'event_language', None):
                    # Persist the currently displayed event language when turning sync off.
                    resp.set_cookie(
                        event_cookie_name,
                        request.event_language,
                        max_age=max_age,
                        expires=_cookie_expires(max_age),
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path='/',
                    )

            locale = validate_language(locale, supported)
            if locale:
                resp.set_cookie(
                    event_cookie_name,
                    locale,
                    max_age=max_age,
                    expires=_cookie_expires(max_age),
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path='/',
                )

                enforce_active = (
                    enforce_ui_language == '1'
                    if enforce_ui_language is not None
                    else request.COOKIES.get(enforce_cookie_name, '0') == '1'
                )
                if enforce_active and locale.lower() != ui_language.lower():
                    resp.set_cookie(
                        enforce_cookie_name,
                        '0',
                        max_age=max_age,
                        expires=_cookie_expires(max_age),
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path='/',
                    )

        return resp
