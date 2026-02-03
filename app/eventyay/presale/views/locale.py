from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View

from eventyay.base.models.event import Event
from eventyay.common.utils.language import get_event_language_cookie_name, validate_language
from eventyay.helpers.cookies import set_cookie_without_samesite

from .robots import NoSearchIndexViewMixin


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
                expires=(datetime.now(timezone.utc) + timedelta(seconds=max_age)).strftime('%a, %d-%b-%Y %H:%M:%S GMT'),
                domain=settings.SESSION_COOKIE_DOMAIN,
            )

        return resp


class EventLocaleSet(NoSearchIndexViewMixin, View):
    def get(self, request, *args, **kwargs):
        url = request.GET.get('next', request.headers.get('Referer', '/'))
        url = url if url_has_allowed_host_and_scheme(url, allowed_hosts=[request.get_host()]) else '/'
        resp = HttpResponseRedirect(url)

        locale = request.GET.get('locale')
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
            supported = event.locales
            locale = validate_language(locale, supported)
            if locale:
                max_age = 10 * 365 * 24 * 60 * 60
                cookie_name = get_event_language_cookie_name(event.slug, event.organizer.slug)
                resp.set_cookie(
                    cookie_name,
                    locale,
                    max_age=max_age,
                    expires=(datetime.now(timezone.utc) + timedelta(seconds=max_age)).strftime('%a, %d-%b-%Y %H:%M:%S GMT'),
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path='/',
                )

        return resp
