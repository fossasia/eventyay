import json
import logging
import os
from mimetypes import guess_type
from pathlib import Path
from typing import cast
from django.shortcuts import redirect
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.encoding import force_str
from django.utils.timezone import now
from django.utils.functional import Promise
from django.utils.translation import gettext as _
from django.views.generic import View
from django.views.static import serve as static_serve
from django_scopes import scope
from i18nfield.strings import LazyI18nString
from eventyay.base.models.room import AnonymousInvite
from eventyay.base.models import Event  # Added for /video event context
from eventyay.agenda.views.utils import build_public_schedule_exporters

VIDEO_DIST_DIR = cast(Path, settings.STATIC_ROOT) / 'video'
logger = logging.getLogger(__name__)


def safe_reverse(name: str, **kw) -> str:
    try:
        return reverse(name, kwargs=kw) if kw else reverse(name)
    except NoReverseMatch as e:
        logger.warning('Video SPA: Could not reverse %s with %s: %s', name, kw, e)
        return '/missing-url-registration/'


class VideoSPAView(View):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs):
        # Now expecting organizer and event from URL pattern: /{organizer}/{event}/video
        organizer_slug = kwargs.get('organizer')
        event_slug = kwargs.get('event')
        event_identifier = kwargs.get('event_identifier')

        # TODO remove debug logging once new video routing is stable
        event = None
        if organizer_slug and event_slug:
            try:
                event = Event.objects.select_related('organizer').get(slug=event_slug, organizer__slug=organizer_slug)
            except Event.DoesNotExist:
                return HttpResponse('Event not found', status=404)

        index_path = VIDEO_DIST_DIR / 'index.html'
        if index_path.is_file():
            html_content = index_path.read_text()
        else:
            html_content = '<!-- /video build missing: {} -->'.format(index_path)

        base_href = '/video/'
        if event:
            # Inject window.venueless config (frontend still expects this name)
            # Mirror structure used in legacy live AppView but adjusted basePath

            # Quick fix: avoid reverse('api:root') which is currently not included -> NoReverseMatch
            api_base = f'/api/v1/events/{event.slug}/'  # TODO replace with reverse once API namespace wired

            # Best effort reverse for optional endpoints

            cfg = event.config or {}

            with scope(event=event):
                schedule = event.current_schedule or event.wip_schedule
                schedule_data = schedule.build_data(all_talks=False, enrich=True) if schedule else None
                schedule_version = schedule.version if schedule else None
                schedule_exporters = build_public_schedule_exporters(event, version=schedule_version)

            base_path = event.urls.video_base.rstrip('/')
            base_href = event.urls.video_base
            injected = {
                'api': {
                    'base': api_base,
                    'socket': '{}://{}/ws/event/{}/'.format(
                        'wss' if request.is_secure() else 'ws',
                        request.get_host(),
                        event.pk,
                    ),
                    'upload': safe_reverse('storage:upload', event_id=event.pk) or '',
                    'scheduleImport': safe_reverse('storage:schedule_import', event_id=event.pk) or '',
                    'systemlog': safe_reverse('live:systemlog') or '',
                },
                'features': getattr(event, 'feature_flags', {}) or {},
                'externalAuthUrl': getattr(event, 'external_auth_url', None),
                'locale': event.locale,
                'date_locale': cfg.get('date_locale', 'en-ie'),
                'theme': cfg.get('theme', {}),
                'video_player': cfg.get('video_player', {}),
                'mux': cfg.get('mux', {}),
                'schedule': schedule_data,
                'scheduleMeta': {
                    'version': schedule_version or '',
                    'is_current': schedule == event.current_schedule if schedule else False,
                    'changelog_url': str(event.urls.changelog),
                    'current_schedule_url': str(event.urls.schedule) if event.current_schedule else '',
                    'versions': [
                        {
                            'version': v,
                            'url': f'{str(event.urls.schedule)}v/{v}/',
                            'isCurrent': v == schedule_version,
                        }
                        for v in event.schedules.filter(version__isnull=False)
                        .order_by('-published')
                        .values_list('version', flat=True)
                    ],
                    'exporters': schedule_exporters,
                },
                # Extra values expected by config.js/theme
                'eventUrl': str(event.urls.base),
                'eventSlug': event.slug,
                'basePath': base_path,
                'defaultLocale': 'en',
                'locales': ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
                'noThemeEndpoint': True,  # Prevent frontend from requesting missing /theme endpoint
                'translationMessages': {
                    'favs_not_logged_in': str(_(
                        "You're currently not logged in, so your favourited talks will only be stored locally in your browser."
                    )),
                    'favs_not_saved': str(_('Your favourites could only be saved locally in your browser.')),
                    'no_matching_options': str(_('Sorry, no matching options.')),
                    'view_changelog': str(_('View Changelog')),
                    'go_to_current_version': str(_('Go to current version')),
                    'reset_all_filters': str(_('Reset all filters')),
                    'sort_by': str(_('Sort')),
                    'sort_by_room': str(_('By room')),
                    'sort_by_title': str(_('A\u2013Z')),
                    'sort_by_popularity': str(_('Most popular')),
                    'fullscreen': str(_('Fullscreen')),
                    'exit_fullscreen': str(_('Exit Fullscreen')),
                    'latest': str(_('Latest')),
                    'version_warning_editable': str(_(
                        'You are currently viewing the editable schedule version.'
                        ' It may not match the released version.'
                    )),
                    'version_warning_old': str(_('You are currently viewing an older schedule version.')),
                    'join_room': str(_('Join room')),
                    'view_video': str(_('View Video')),
                    'watch_live': str(_('Watch live')),
                    'speaker_fallback': str(_('Speaker')),
                    'speaker_name_not_provided': str(_('Speaker name not provided')),
                    'add_to_calendar': str(_('Add to Calendar')),
                    'ical': str(_('iCal')),
                    'json': str(_('JSON')),
                    'xml': str(_('XML')),
                    'xcal': str(_('XCal')),
                    'google_calendar': str(_('Google Calendar')),
                    'webcal': str(_('Webcal')),
                    'yes': str(_('Yes')),
                    'no': str(_('No')),
                    'no_speakers_found': str(_('No speakers found.')),
                    'sessions': str(_('Sessions')),
                    'tracks': str(_('Tracks')),
                    'speakers': str(_('Speakers')),
                    'downloads': str(_('Downloads')),
                    'starred_by': str(_('Starred by')),
                    'starred': str(_('Starred')),
                    'export': str(_('Export')),
                    'exports': str(_('Exports')),
                    'no_file_provided': str(_('No file provided')),
                    'no_response': str(_('No response')),
                    'other_timezones': str(_('Other Timezones')),
                    'current': str(_('current')),
                    'print': str(_('Print')),
                    'list_view': str(_('List View')),
                    'calendar_view': str(_('Calendar View')),
                    'search': str(_('Search')),
                    'featured_speakers': str(_('Featured Speakers')),
                    'view_profile': str(_('View speaker profile')),
                    'no_starred_sessions': str(_('No starred sessions.')),
                },
            }

            class EventyayJSONEncoder(DjangoJSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (Promise, LazyI18nString)):
                        return force_str(obj)
                    return super().default(obj)

            extra_script = f'<script>window.eventyay={json.dumps(injected, cls=EventyayJSONEncoder)}</script>'
            # Inject extra_script before the first <script ...> occurrence (handles attributes like type/src)
            lower_html = html_content.lower()
            before, sep, _rest = lower_html.partition('<script ')
            if sep:
                idx = len(before)
                html_content = f'{html_content[:idx]}{extra_script}{html_content[idx:]}'
            else:
                html_content = f'{extra_script}{html_content}'

        elif event_identifier:
            # Event identifier provided but not found -> 404
            return HttpResponse('Event not found', status=404)

        if '<base ' not in html_content.lower():
            # Ensure assets resolve correctly regardless of nested route
            html_content = html_content.replace('<head>', f'<head><base href="{base_href}">', 1)

        resp = HttpResponse(html_content, content_type='text/html')
        resp._csp_ignore = True  # Disable CSP for SPA (relies on dynamic inline scripts)
        return resp


class VideoAssetView(View):
    def get(self, request, path='', *args, **kwargs):
        # Accept empty path -> index handling done by SPA view
        candidate_paths = (
            [
                os.path.join(VIDEO_DIST_DIR, path),
                os.path.join(VIDEO_DIST_DIR, 'assets', path),
            ]
            if path
            else []
        )
        for fp in candidate_paths:
            if os.path.isfile(fp):
                rel = os.path.relpath(fp, VIDEO_DIST_DIR)
                resp = static_serve(request, rel, document_root=VIDEO_DIST_DIR)
                resp._csp_ignore = True
                # Ensure proper content type for module scripts
                ctype, _rest = guess_type(fp)
                if ctype:
                    resp['Content-Type'] = ctype
                return resp
        logger.warning('Video asset not found: %s', path)
        raise Http404()

class AnonymousInviteRedirectView(View):
    """
    Handle anonymous room invite short tokens (e.g., /eGHhXr/).
    Redirects to the video SPA standalone anonymous room view:
    /{organizer}/{event}/video/standalone/{room_id}/anonymous#invite={token}
    """
    def get(self, request, token, *args, **kwargs):
        try:
            invite = AnonymousInvite.objects.select_related(
                'event', 'event__organizer', 'room'
            ).get(
                short_token=token,
                expires__gte=now(),
            )
        except AnonymousInvite.DoesNotExist:
            raise Http404("Invalid or expired anonymous room link")

        # Build redirect URL to the video SPA standalone anonymous view
        event = invite.event
        organizer_slug = event.organizer.slug
        event_slug = event.slug
        room_id = invite.room_id

        # Redirect to /{organizer}/{event}/video/standalone/{room_id}/anonymous#invite={token}
        redirect_url = f"/{organizer_slug}/{event_slug}/video/standalone/{room_id}/anonymous#invite={token}"
        return redirect(redirect_url)

