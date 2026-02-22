import io
import json
from collections import defaultdict
from urllib.parse import quote, urlparse

import vobject
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import Storage
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.generic import DetailView, ListView, TemplateView, View
from django_context_decorator import context
from i18nfield.utils import I18nJSONEncoder

from eventyay.common.text.path import safe_filename
from eventyay.common.urls import get_base_url
from eventyay.common.utils.language import localize_event_text
from eventyay.common.views.mixins import (
    EventPermissionRequired,
    Filterable,
    PermissionRequired,
    SocialMediaCardMixin,
)
from eventyay.agenda.views.utils import escape_json_for_script, is_public_speakers_empty, redirect_to_presale_with_warning
from eventyay.base.models import SpeakerProfile, User
from eventyay.base.models import TalkQuestionTarget


class ScheduleDataMixin:
    """Provide schedule_json context for pages that embed the schedule widget."""

    @context
    def schedule_json(self):
        schedule = self.request.event.current_schedule
        if not schedule:
            return '{}'
        data = schedule.build_data(enrich=True)
        return escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))


class SpeakerList(ScheduleDataMixin, EventPermissionRequired, Filterable, ListView):
    context_object_name = 'speakers'
    template_name = 'agenda/speakers.html'
    permission_required = 'base.list_schedule'
    default_filters = ('user__fullname__icontains',)

    def dispatch(self, request, *args, **kwargs):
        if is_public_speakers_empty(request):
            return redirect_to_presale_with_warning(request, _('No published speakers.'))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            SpeakerProfile.objects.filter(user__in=self.request.event.speakers, event=self.request.event)
            .select_related('user', 'event', 'event__organizer')
            .order_by('user__fullname')
        )
        qs = self.filter_queryset(qs)

        speaker_mapping = defaultdict(list)
        for talk in self.request.event.talks.all().prefetch_related('speakers'):
            for speaker in talk.speakers.all():
                speaker_mapping[speaker.code].append(talk)

        for profile in qs:
            profile.talks = speaker_mapping[profile.user.code]
        return qs

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class SpeakerView(ScheduleDataMixin, PermissionRequired, TemplateView):
    template_name = 'agenda/speaker.html'
    permission_required = 'base.view_speakerprofile'
    slug_field = 'code'

    def dispatch(self, request, *args, **kwargs):
        if is_public_speakers_empty(request):
            return redirect_to_presale_with_warning(request, _('No published speakers.'))
        return super().dispatch(request, *args, **kwargs)

    @context
    @cached_property
    def profile(self):
        return (
            SpeakerProfile.objects.filter(event=self.request.event, user__code__iexact=self.kwargs['code'])
            .select_related('user', 'event', 'event__organizer')
            .first()
        )

    @context
    @cached_property
    def talks(self):
        if not self.request.event.current_schedule:
            return []
        return (
            self.request.event.current_schedule.talks.filter(
                submission__speakers__code=self.kwargs['code'], is_visible=True
            )
            .select_related('submission', 'room', 'submission__event', 'submission__event__organizer')
            .prefetch_related('submission__speakers')
        )

    def get_permission_object(self):
        return self.profile

    @context
    def answers(self):
        return self.profile.user.answers.filter(
            question__is_public=True,
            question__event=self.request.event,
            question__target=TalkQuestionTarget.SPEAKER,
        ).select_related('question')


class SpeakerRedirect(DetailView):
    model = User

    def dispatch(self, request, **kwargs):
        speaker = self.get_object()
        profile = speaker.profiles.filter(event=self.request.event).first()
        if profile and self.request.user.has_perm('base.view_speakerprofile', profile):
            return redirect(profile.urls.public.full())
        raise Http404()


class SpeakerTalksIcalView(PermissionRequired, DetailView):
    context_object_name = 'profile'
    permission_required = 'base.view_speakerprofile'
    slug_field = 'code'

    def get_object(self, queryset=None):
        return SpeakerProfile.objects.filter(event=self.request.event, user__code__iexact=self.kwargs['code']).first()

    def get(self, request, event, *args, **kwargs):
        if not self.request.event.current_schedule:
            raise Http404()
        netloc = urlparse(settings.SITE_URL).netloc
        speaker = self.get_object()
        slots = self.request.event.current_schedule.talks.filter(
            submission__speakers=speaker.user, is_visible=True
        ).select_related('room', 'submission')

        cal = vobject.iCalendar()
        cal.add('prodid').value = f'-//eventyay//{netloc}//{request.event.slug}//{speaker.code}'

        for slot in slots:
            slot.build_ical(cal)

        try:
            speaker_name = Storage().get_valid_name(name=speaker.user.fullname or speaker.user.code)
        except SuspiciousFileOperation:
            speaker_name = Storage().get_valid_name(name=speaker.user.code)
        return HttpResponse(
            cal.serialize(),
            content_type='text/calendar',
            headers={
                'Content-Disposition': f'attachment; filename="{request.event.slug}-{safe_filename(speaker_name)}.ics"'
            },
        )


class SpeakerTalksExportView(EventPermissionRequired, View):
    """Export a speaker's talks in JSON, XML, or XCal format."""

    permission_required = 'base.list_schedule'

    def get_speaker_and_slots(self, request):
        speaker = SpeakerProfile.objects.filter(
            event=request.event, user__code__iexact=self.kwargs['code']
        ).select_related('user').first()
        if not speaker:
            raise Http404()
        schedule = request.event.current_schedule
        if not schedule:
            raise Http404()
        slots = schedule.talks.filter(
            submission__speakers=speaker.user, is_visible=True
        ).select_related(
            'room', 'submission', 'submission__track', 'submission__submission_type'
        ).prefetch_related('submission__speakers', 'submission__resources')
        return speaker, slots

    def get(self, request, event, **kwargs):
        fmt = kwargs.get('format', '')
        handler = {
            'json': self.render_json,
            'xml': self.render_xml,
            'xcal': self.render_xcal,
        }.get(fmt)
        if not handler:
            raise Http404
        speaker, slots = self.get_speaker_and_slots(request)
        return handler(request, speaker, slots)

    def render_json(self, request, speaker, slots):
        event = request.event
        base_url = get_base_url(event)
        talks_data = []
        for slot in slots:
            sub = slot.submission
            talks_data.append({
                'guid': slot.uuid,
                'code': sub.code,
                'id': sub.id,
                'date': slot.local_start.isoformat(),
                'start': f'{slot.local_start:%H:%M}',
                'duration': slot.export_duration,
                'room': localize_event_text(slot.room.name) if slot.room else None,
                'slug': slot.frab_slug,
                'url': sub.urls.public.full(),
                'title': localize_event_text(sub.title),
                'track': localize_event_text(sub.track.name) if sub.track else None,
                'type': localize_event_text(sub.submission_type.name),
                'language': sub.content_locale,
                'abstract': localize_event_text(sub.abstract),
                'description': localize_event_text(sub.description),
                'do_not_record': sub.do_not_record,
                'persons': [
                    {
                        'code': p.code,
                        'name': p.get_display_name(),
                        'biography': localize_event_text(p.event_profile(event).biography),
                    }
                    for p in sub.speakers.all()
                ],
                'links': [
                    {'title': localize_event_text(r.description), 'url': r.link}
                    for r in sub.resources.all() if r.link
                ],
                'attachments': [
                    {'title': localize_event_text(r.description), 'url': r.resource.url}
                    for r in sub.resources.all() if not r.link
                ],
            })
        data = {
            'speaker': speaker.user.code,
            'base_url': base_url,
            'talks': talks_data,
        }
        return JsonResponse(data, encoder=I18nJSONEncoder)

    def render_xml(self, request, speaker, slots):
        base_url = get_base_url(request.event)
        context = {
            'talk_slots': slots,
            'event': request.event,
            'base_url': base_url,
        }
        content = get_template('agenda/single_talk.xml').render(context=context)
        return HttpResponse(content, content_type='text/xml')

    def render_xcal(self, request, speaker, slots):
        url = get_base_url(request.event)
        domain = urlparse(url).netloc
        context = {
            'talk_slots': slots,
            'url': url,
            'domain': domain,
        }
        content = get_template('agenda/single_talk.xcal').render(context=context)
        return HttpResponse(content, content_type='text/xml')


class SpeakerTalksCalendarRedirectView(EventPermissionRequired, View):
    """Redirect to Google Calendar or Webcal for a speaker's talks."""

    permission_required = 'base.list_schedule'

    def get(self, request, event, **kwargs):
        provider = kwargs.get('provider', '')
        speaker = SpeakerProfile.objects.filter(
            event=request.event, user__code__iexact=self.kwargs['code']
        ).select_related('user').first()
        if not speaker:
            raise Http404()
        schedule = request.event.current_schedule
        if not schedule:
            raise Http404()
        slots = schedule.talks.filter(
            submission__speakers=speaker.user, is_visible=True
        ).select_related('room', 'submission')
        if not slots.exists():
            raise Http404()

        if provider == 'google-calendar':
            slot = slots.first()
            return self.google_calendar_redirect(slot, request)
        if provider == 'webcal':
            ical_url = request.build_absolute_uri(
                reverse('agenda:speaker.talks.ical', kwargs={
                    'organizer': request.event.organizer.slug,
                    'event': event,
                    'code': self.kwargs['code'],
                })
            )
            webcal_url = ical_url.replace('https://', 'webcal://').replace('http://', 'webcal://')
            return HttpResponseRedirect(webcal_url)
        raise Http404()

    def google_calendar_redirect(self, slot, request):
        sub = slot.submission
        start = slot.start
        end = slot.real_end
        dates = f'{start:%Y%m%dT%H%M%SZ}/{end:%Y%m%dT%H%M%SZ}'
        title = localize_event_text(sub.title)
        location = localize_event_text(slot.room.name) if slot.room else ''
        details = localize_event_text(sub.abstract) or ''
        url = (
            'https://calendar.google.com/calendar/render?action=TEMPLATE'
            f'&text={quote(str(title))}'
            f'&dates={dates}'
            f'&location={quote(str(location))}'
            f'&details={quote(str(details))}'
        )
        return HttpResponseRedirect(url)


class SpeakerSocialMediaCard(SocialMediaCardMixin, SpeakerView):
    def get_image(self):
        return self.profile.avatar


@cache_page(60 * 60)
def empty_avatar_view(request, organizer=None, event=None):
    # cached for an hour
    color = request.event.visible_primary_color or settings.DEFAULT_EVENT_PRIMARY_COLOR
    avatar_template = f"""<svg
   xmlns="http://www.w3.org/2000/svg"
   viewBox="0 0 100 100">
  <g>
    <path
       id="body"
       d="m 2,98 h 96 0 c 0,0 6,-65 -48,-52 c 0,0 -54,-10 -48,52"
       style="fill:none;stroke:{color};stroke-width:1.6;stroke-linecap:butt;stroke-linejoin:round;stroke-miterlimit:4;stroke-dasharray:2.1, 2.1;stroke-dashoffset:0;stroke-opacity:0.87" />
    <ellipse
       ry="27"
       rx="27"
       cy="28"
       cx="50"
       id="heady"
       style="fill:#ffffff;stroke:{color};stroke-width:1.3;stroke-linecap:butt;stroke-linejoin:round;stroke-miterlimit:4;stroke-dasharray:6.5, 8;stroke-dashoffset:4;stroke-opacity:0.87" />
  </g>
</svg>"""
    return FileResponse(
        io.BytesIO(avatar_template.encode()),
        as_attachment=True,
        content_type='image/svg+xml',
    )
