from __future__ import annotations

from collections import defaultdict, namedtuple
from contextlib import suppress
from datetime import UTC
from functools import lru_cache
from typing import TYPE_CHECKING
from urllib.parse import quote
from xml.etree.ElementTree import tostring as xml_tostring

import qrcode as qr_lib
from django.conf import settings
from django.db import models, transaction
from django.db.models import Count
from django.db.utils import DatabaseError
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_scopes import scope
from i18nfield.fields import I18nTextField
from qrcode.image.svg import SvgPathFillImage

from eventyay.agenda.export_resources import enriched_resource_entry
from eventyay.agenda.signals import register_recording_provider
from eventyay.agenda.tasks import export_schedule_html
from eventyay.common.text.phrases import phrases
from eventyay.common.urls import EventUrls
from eventyay.schedule.notifications import render_notifications
from eventyay.schedule.signals import schedule_release
from eventyay.talk_rules.agenda import (
    can_view_schedule,
    can_view_wip_schedule,
    is_agenda_visible,
    is_widget_visible,
)
from eventyay.talk_rules.submission import is_wip, orga_can_change_submissions

from .auth import (
    User,
)

# We use relative imports here to avoid circular imports.
from .availability import Availability
from .mail import MailTemplateRoles
from .mixins import PretalxModel
from .profile import SpeakerProfile
from .slot import TalkSlot
from .stream_schedule import StreamSchedule
from .submission import Submission, SubmissionFavourite, SubmissionStates


if TYPE_CHECKING:
    from .room import Room
    from .track import Track


@lru_cache(maxsize=16384)
def make_qr_svg(url: str) -> str:
    """Generate an SVG QR code string for the given URL.

    Results are cached because the same export URLs are generated on every
    schedule page load and QR encoding is CPU-intensive. The cache needs to
    be large enough to hold (6 exports × talks) + (6 exports × speakers)
    entries for the biggest event on a given process; 512 thrashed on
    mid-sized events.
    """
    image = qr_lib.make(url, image_factory=SvgPathFillImage)
    return xml_tostring(image.get_image()).decode()


def make_talk_qr_map(base_url: str, code: str) -> dict:
    """Return the QR-code SVG dict for a single talk's export URLs."""
    b = base_url.rstrip('/')
    return {
        'ics': make_qr_svg(f'{b}/talk/{code}.ics'),
        'json': make_qr_svg(f'{b}/talk/{code}.json'),
        'xml': make_qr_svg(f'{b}/talk/{code}.xml'),
        'xcal': make_qr_svg(f'{b}/talk/{code}.xcal'),
        'google_calendar': make_qr_svg(f'{b}/talk/{code}/export/google-calendar'),
        'webcal': make_qr_svg(f'{b}/talk/{code}/export/webcal'),
    }


def make_speaker_qr_map(speaker_base_url: str) -> dict:
    """Return the QR-code SVG dict for a speaker's talks export URLs."""
    b = speaker_base_url.rstrip('/')
    return {
        'ics': make_qr_svg(f'{b}/talks.ics'),
        'json': make_qr_svg(f'{b}/talks.json'),
        'xml': make_qr_svg(f'{b}/talks.xml'),
        'xcal': make_qr_svg(f'{b}/talks.xcal'),
        'google_calendar': make_qr_svg(f'{b}/talks/export/google-calendar'),
        'webcal': make_qr_svg(f'{b}/talks/export/webcal'),
    }


class Schedule(PretalxModel):
    """The Schedule model contains all scheduled.

    :class:`~pretalx.schedule.models.slot.TalkSlot` objects (visible or not)
    for a schedule release for an :class:`~pretalx.event.models.event.Event`.

    :param published: ``None`` if the schedule has not been published yet.
    """

    event = models.ForeignKey(to='Event', on_delete=models.PROTECT, related_name='schedules')
    version = models.CharField(
        max_length=190,
        null=True,
        blank=True,
        verbose_name=pgettext_lazy('Version of the conference schedule', 'Version'),
    )
    published = models.DateTimeField(null=True, blank=True)
    comment = I18nTextField(
        null=True,
        blank=True,
        help_text=_('This text will be shown in the public changelog and the RSS feed.')
        + ' '
        + phrases.base.use_markdown,
    )
    if TYPE_CHECKING:
        talks: models.ManyToManyField[TalkSlot, models.Model]

    class Meta:
        ordering = ('-published',)
        unique_together = (('event', 'version'),)
        rules_permissions = {
            'list': (~is_wip & can_view_schedule) | can_view_wip_schedule,
            'view_widget': is_widget_visible | can_view_wip_schedule,
            'view': (~is_wip & is_agenda_visible) | can_view_wip_schedule,
            'orga_view': can_view_wip_schedule,
            'release': orga_can_change_submissions,
        }

    class urls(EventUrls):
        """URL patterns for schedule views."""

        public = '{self.event.urls.schedule}v/{self.url_version}/'
        widget_data = '{public}widgets/schedule.json'
        nojs = '{public}nojs'

    @transaction.atomic
    def freeze(self, name: str, user=None, notify_speakers: bool = True, comment: str = None):
        """Releases the current WIP schedule as a fixed schedule version.

        :param name: The new schedule name. May not be in use in this event,
            and cannot be 'wip' or 'latest'.
        :param user: The :class:`~pretalx.person.models.user.User` initiating
            the freeze.
        :param notify_speakers: Should notification emails for speakers with
            changed slots be generated?
        :param comment: Public comment for the release
        :rtype: Schedule
        """

        if name in ('wip', 'latest'):
            raise Exception(f'Cannot use reserved name "{name}" for schedule version.')
        if self.version:
            raise Exception(f'Cannot freeze schedule version: already versioned as "{self.version}".')
        if not name:
            raise Exception('Cannot create schedule version without a version name.')

        self.version = name
        self.comment = comment
        self.published = now()

        # Create WIP schedule first, to avoid race conditions
        wip_schedule = Schedule.objects.create(event=self.event)

        self.save(update_fields=['published', 'version', 'comment'])
        self.log_action('eventyay.schedule.release', person=user, orga=True)

        # Set visibility
        self.talks.all().update(is_visible=False)
        self.talks.filter(
            models.Q(submission__state=SubmissionStates.CONFIRMED) | models.Q(submission__isnull=True),
            start__isnull=False,
        ).update(is_visible=True)

        talks = []
        for talk in self.talks.select_related('submission', 'room').all():
            talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(talks)

        if notify_speakers:
            self.generate_notifications(save=True)

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule
        with suppress(AttributeError):
            del wip_schedule.event.current_schedule

        schedule_release.send_robust(self.event, schedule=self, user=user)

        if self.event.get_feature_flag('export_html_on_release'):
            if not settings.CELERY_TASK_ALWAYS_EAGER:
                export_schedule_html.apply_async(kwargs={'event_id': self.event.id}, ignore_result=True)
            else:
                self.event.cache.set('rebuild_schedule_export', True, None)
        return self, wip_schedule

    freeze.alters_data = True

    @transaction.atomic
    def unfreeze(self, user=None):
        """Resets the current WIP schedule to an older schedule version."""

        if not self.version:
            raise Exception('Cannot unfreeze schedule version: not released yet.')

        # collect all talks, which have been added since this schedule (#72)
        submission_ids = self.talks.all().values_list('submission_id', flat=True)
        talks = self.event.wip_schedule.talks.exclude(submission_id__in=submission_ids)
        try:
            talks = list(talks.union(self.talks.all()))  # We force evaluation to catch the DatabaseError early
        except DatabaseError:  # SQLite cannot deal with ordered querysets in union()
            talks = set(talks) | set(self.talks.all())

        wip_schedule = Schedule.objects.create(event=self.event)
        new_talks = []
        for talk in talks:
            new_talks.append(talk.copy_to_schedule(wip_schedule, save=False))
        TalkSlot.objects.bulk_create(new_talks)

        self.event.wip_schedule.talks.all().delete()
        self.event.wip_schedule.delete()

        with suppress(AttributeError):
            del wip_schedule.event.wip_schedule

        return self, wip_schedule

    unfreeze.alters_data = True

    @cached_property
    def scheduled_talks(self):
        """Returns all :class:`~pretalx.schedule.models.slot.TalkSlot` objects
        that have been scheduled and are visible in the schedule (that is, have
        been confirmed at the time of release)."""

        return (
            self.talks.select_related(
                'submission',
                'submission__event',
                'room',
            )
            .prefetch_related('submission__speakers')
            .filter(
                room__isnull=False,
                room__deleted=False,
                room__is_unscheduled=False,
                start__isnull=False,
                is_visible=True,
                submission__isnull=False,
            )
            .exclude(submission__state=SubmissionStates.DELETED)
        )

    @cached_property
    def breaks(self):
        return self.talks.select_related('room').filter(submission__isnull=True, room__deleted=False, room__is_unscheduled=False)

    @cached_property
    def slots(self):
        """Returns all.

        :class:`~pretalx.submission.models.submission.Submission` objects with
        :class:`~pretalx.schedule.models.slot.TalkSlot` objects in this
        schedule.
        """

        return Submission.objects.filter(id__in=self.scheduled_talks.values_list('submission', flat=True))

    @cached_property
    def previous_schedule(self):
        """Returns the schedule released before this one, if any."""
        queryset = self.event.schedules.exclude(pk=self.pk)
        if self.published:
            queryset = queryset.filter(published__lt=self.published)
        return queryset.order_by('-published').first()

    def _handle_submission_move(self, submission, old_slots, new_slots, all_old_slots=None, all_new_slots=None):
        new = []
        canceled = []
        moved = []
        if all_old_slots is None:
            all_old_slots = [slot for slot in old_slots.values() if slot.submission_id == submission.pk]
        if all_new_slots is None:
            all_new_slots = [slot for slot in new_slots.values() if slot.submission_id == submission.pk]
        new_sigs = {(slot.room_id, slot.start, slot.end) for slot in all_new_slots}
        old_sigs = {(slot.room_id, slot.start, slot.end) for slot in all_old_slots}
        old_slots = [slot for slot in all_old_slots if (slot.room_id, slot.start, slot.end) not in new_sigs]
        new_slots = [slot for slot in all_new_slots if (slot.room_id, slot.start, slot.end) not in old_sigs]
        diff = len(old_slots) - len(new_slots)
        if diff > 0:
            canceled = old_slots[:diff]
            old_slots = old_slots[diff:]
        elif diff < 0:
            diff = -diff
            new = new_slots[:diff]
            new_slots = new_slots[diff:]
        for move in zip(old_slots, new_slots):
            old_slot = move[0]
            new_slot = move[1]
            moved.append(
                {
                    'submission': new_slot.submission,
                    'old_start': old_slot.local_start,
                    'new_start': new_slot.local_start,
                    'old_room': old_slot.room.name,
                    'new_room': new_slot.room.name,
                    'new_info': new_slot.room.speaker_info,
                    'new_slot': new_slot,
                }
            )
        return new, canceled, moved

    @cached_property
    def changes(self) -> dict:
        """Returns a dictionary of changes when compared to the previous
        version.

        The ``action`` field is either ``create`` or ``update``. If it's
        an update, the ``count`` integer, and the ``new_talks``,
        ``canceled_talks`` and ``moved_talks`` lists are also present.
        """
        result = {
            'count': 0,
            'action': 'update',
            'new_talks': [],
            'canceled_talks': [],
            'moved_talks': [],
        }
        if not self.previous_schedule:
            result['action'] = 'create'
            return result

        Slot = namedtuple('Slot', ['submission', 'room', 'local_start'])
        old_slots = {
            Slot(slot.submission, slot.room, slot.local_start): slot for slot in self.previous_schedule.scheduled_talks
        }
        new_slots = {Slot(slot.submission, slot.room, slot.local_start): slot for slot in self.scheduled_talks}

        old_slot_set = set(old_slots.keys())
        new_slot_set = set(new_slots.keys())
        old_submissions = {slot.submission for slot in old_slots}
        new_submissions = {slot.submission for slot in new_slots}
        handled_submissions = set()
        new_by_submission = defaultdict(list)
        old_by_submission = defaultdict(list)
        for slot in new_slot_set:
            new_by_submission[slot.submission].append(new_slots[slot])
        for slot in old_slot_set:
            old_by_submission[slot.submission].append(old_slots[slot])

        moved_or_missing = old_slot_set - new_slot_set - {None}
        moved_or_new = new_slot_set - old_slot_set - {None}

        for entry in moved_or_missing:
            if entry.submission in handled_submissions or not entry.submission:
                continue
            if entry.submission not in new_submissions:
                result['canceled_talks'] += old_by_submission[entry.submission]
            else:
                new, canceled, moved = self._handle_submission_move(
                    entry.submission,
                    old_slots,
                    new_slots,
                    all_old_slots=old_by_submission.get(entry.submission, []),
                    all_new_slots=new_by_submission.get(entry.submission, []),
                )
                result['new_talks'] += new
                result['canceled_talks'] += canceled
                result['moved_talks'] += moved
            handled_submissions.add(entry.submission)
        for entry in moved_or_new:
            if entry.submission in handled_submissions:
                continue
            if entry.submission not in old_submissions:
                result['new_talks'] += new_by_submission[entry.submission]
            else:
                new, canceled, moved = self._handle_submission_move(
                    entry.submission,
                    old_slots,
                    new_slots,
                    all_old_slots=old_by_submission.get(entry.submission, []),
                    all_new_slots=new_by_submission.get(entry.submission, []),
                )
                result['new_talks'] += new
                result['canceled_talks'] += canceled
                result['moved_talks'] += moved
            handled_submissions.add(entry.submission)

        result['count'] = len(result['new_talks']) + len(result['canceled_talks']) + len(result['moved_talks'])
        return result

    @cached_property
    def use_room_availabilities(self):
        return Availability.objects.filter(room__isnull=False, event=self.event).exists

    def get_talk_warnings(
        self,
        talk,
        with_speakers=True,
        room_avails=None,
        speaker_avails=None,
        speaker_profiles=None,
        room_overlap_ids=None,
        speaker_overlaps_by_talk=None,
    ) -> list:
        """A list of warnings that apply to this slot.

        Warnings are dictionaries with a ``type`` (``room`` or
        ``speaker``, for now) and a ``message`` fit for public display.
        This property only shows availability based warnings.
        """

        if not talk.start or not talk.submission or not talk.room:
            return []
        warnings = []
        availability = talk.as_availability
        url = talk.submission.orga_urls.base
        if self.use_room_availabilities:
            if room_avails is None:
                room_avails = talk.room.availabilities.all()
            if room_avails and not any(
                room_availability.contains(availability) for room_availability in Availability.union(room_avails)
            ):
                warnings.append(
                    {
                        'type': 'room',
                        'message': str(_('Room {room_name} is not available at the scheduled time.')).format(
                            room_name=f'{phrases.base.quotation_open}{talk.room.name}{phrases.base.quotation_close}'
                        ),
                        'url': url,
                    }
                )
        if room_overlap_ids is not None:
            overlaps = talk.pk in room_overlap_ids
        else:
            overlaps = (
                TalkSlot.objects.filter(schedule=self, room=talk.room)
                .filter(
                    models.Q(start__lt=talk.start, end__gt=talk.start)
                    | models.Q(start__lt=talk.real_end, end__gt=talk.real_end)
                    | models.Q(start__gt=talk.start, end__lt=talk.real_end)
                    | models.Q(start=talk.start, end=talk.real_end)
                )
                .exclude(pk=talk.pk)
                .exists()
            )
        if overlaps:
            warnings.append(
                {
                    'type': 'room_overlap',
                    'message': _('Another session in the same room overlaps with this one.'),
                    'url': url,
                }
            )

        for speaker in talk.submission.speakers.all():
            if with_speakers:
                if speaker_profiles:
                    profile = speaker_profiles.get(speaker)
                else:
                    profile = speaker.event_profile(self.event)
                if profile and speaker_avails is not None:
                    profile_availabilities = speaker_avails.get(profile.pk)
                else:
                    profile_availabilities = list(profile.availabilities.all()) if profile else []
                if profile_availabilities and not any(
                    speaker_availability.contains(availability)
                    for speaker_availability in Availability.union(profile_availabilities)
                ):
                    warnings.append(
                        {
                            'type': 'speaker',
                            'speaker': {
                                'name': speaker.get_display_name(),
                                'code': speaker.code,
                            },
                            'message': str(_('{speaker} is not available at the scheduled time.')).format(
                                speaker=speaker.get_display_name()
                            ),
                            'url': url,
                        }
                    )
            if speaker_overlaps_by_talk is not None:
                overlaps = speaker.pk in speaker_overlaps_by_talk.get(talk.pk, ())
            else:
                overlaps = (
                    TalkSlot.objects.filter(schedule=self, submission__speakers__in=[speaker])
                    .exclude(pk=talk.pk)
                    .filter(
                        models.Q(start__lt=talk.start, end__gt=talk.start)
                        | models.Q(start__lt=talk.real_end, end__gt=talk.real_end)
                        | models.Q(start__gt=talk.start, end__lt=talk.real_end)
                        | models.Q(start=talk.start, end=talk.real_end)
                    )
                    .exists()
                )
            if overlaps:
                warnings.append(
                    {
                        'type': 'speaker',
                        'speaker': {
                            'name': speaker.get_display_name(),
                            'code': speaker.code,
                        },
                        'message': str(_('{speaker} is scheduled for another session at the same time.')).format(
                            speaker=speaker.get_display_name()
                        ),
                        'url': url,
                    }
                )

        return warnings

    def get_all_talk_warnings(self, ids=None, filter_updated=None):
        talks = (
            self.talks.filter(
                submission__isnull=False,
                start__isnull=False,
                room__isnull=False,
                room__deleted=False,
            )
            .select_related(
                'submission',
                'room',
                'submission__event',
                'schedule__event',
            )
            .prefetch_related('submission__speakers')
        )
        if filter_updated:
            talks = talks.filter(updated__gte=filter_updated)
        with_speakers = self.event.cfp.request_availabilities
        room_avails = defaultdict(
            list,
            {room.pk: room.availabilities.all() for room in self.event.rooms.all().prefetch_related('availabilities')},
        )
        speaker_avails = None
        speaker_profiles = None
        if with_speakers:
            speaker_profiles = {
                profile.user: profile
                for profile in SpeakerProfile.objects.filter(event=self.event).select_related('user')
            }
            speaker_avails = defaultdict(
                list,
                {
                    profile.pk: profile.availabilities.all()
                    for profile in SpeakerProfile.objects.filter(event=self.event).prefetch_related('availabilities')
                },
            )
        talk_list = list(talks)
        # Only scan the rest of the schedule when we have a subset to emit for.
        # This keeps the incremental `since=...` polling path cheap: if no talks
        # were updated since the last poll, we do no extra work here.
        if talk_list:
            is_full_scan = not filter_updated
            subset_pks = None if is_full_scan else {t.pk for t in talk_list}
            # Include break slots (submission is null) in the scan set so that
            # sessions conflicting with a scheduled break still produce a
            # room_overlap warning — matching the per-talk ``.exists()`` query
            # at get_talk_warnings() which scans all TalkSlots in the room.
            extra_slots_qs = (
                self.talks.filter(start__isnull=False, room__isnull=False, room__deleted=False)
                .select_related('submission')
                .prefetch_related('submission__speakers')
            )
            if is_full_scan:
                extra_slots_qs = extra_slots_qs.filter(submission__isnull=True)
            else:
                extra_slots_qs = extra_slots_qs.exclude(pk__in=subset_pks)
            scan_set = talk_list + list(extra_slots_qs)
            room_overlap_ids, speaker_overlaps_by_talk = self._compute_overlap_maps(scan_set, subset_pks=subset_pks)
        else:
            room_overlap_ids, speaker_overlaps_by_talk = set(), {}
        result = {}
        for talk in talk_list:
            talk_warnings = self.get_talk_warnings(
                talk=talk,
                with_speakers=with_speakers,
                room_avails=room_avails.get(talk.room_id) if talk.room_id else None,
                speaker_avails=speaker_avails,
                speaker_profiles=speaker_profiles,
                room_overlap_ids=room_overlap_ids,
                speaker_overlaps_by_talk=speaker_overlaps_by_talk,
            )
            if talk_warnings:
                result[talk] = talk_warnings
        return result

    def _compute_overlap_maps(self, talks, subset_pks=None):
        """Compute room- and speaker-overlap sets for the given scheduled talks.

        Replaces per-talk ``.exists()`` probes in ``get_talk_warnings`` with a single
        scan over all scheduled slots and the prefetched speakers. Preserves the
        original query's semantics: strict-inequality overlap plus exact-bounds match.

        If ``subset_pks`` is provided, the ``talks`` argument is expected to contain
        the full scan set (every relevant scheduled slot), while results are only
        emitted for talks whose pk is in ``subset_pks``. This keeps overlap detection
        schedule-wide even when the caller only wants warnings for a subset.

        Caller contract: every element of ``talks`` must have ``submission`` selected
        and ``submission__speakers`` prefetched; otherwise iterating speakers here
        regresses to an N+1. Break slots (``submission_id`` is NULL) are allowed and
        contribute to room-overlap detection only.
        """

        def is_overlap(a_start, a_end, b_start, b_end):
            return (
                (b_start < a_start and b_end > a_start)
                or (b_start < a_end and b_end > a_end)
                or (b_start > a_start and b_end < a_end)
                or (b_start == a_start and b_end == a_end)
            )

        by_room = defaultdict(list)
        by_speaker = defaultdict(list)
        for talk in talks:
            entry = (talk.pk, talk.start, talk.real_end)
            if talk.room_id:
                by_room[talk.room_id].append(entry)
            # Break slots have no submission/speakers — they contribute to
            # room-overlap detection only.
            if talk.submission_id:
                for speaker in talk.submission.speakers.all():
                    by_speaker[speaker.pk].append(entry)

        room_overlap_ids = set()
        speaker_overlaps_by_talk = defaultdict(set)

        if subset_pks is None:
            # Full-schedule scan: O(bucket²) pairwise check per room/speaker.
            for entries in by_room.values():
                for i, (pk_a, start_a, end_a) in enumerate(entries):
                    for pk_b, start_b, end_b in entries[i + 1 :]:
                        if is_overlap(start_a, end_a, start_b, end_b):
                            room_overlap_ids.add(pk_a)
                            room_overlap_ids.add(pk_b)
            for speaker_pk, entries in by_speaker.items():
                for i, (pk_a, start_a, end_a) in enumerate(entries):
                    for pk_b, start_b, end_b in entries[i + 1 :]:
                        if is_overlap(start_a, end_a, start_b, end_b):
                            speaker_overlaps_by_talk[pk_a].add(speaker_pk)
                            speaker_overlaps_by_talk[pk_b].add(speaker_pk)
            return room_overlap_ids, speaker_overlaps_by_talk

        # Subset scan: only probe subset talks against their own room/speaker
        # buckets. Scales with |subset| × bucket size, not |schedule|².
        for entries in by_room.values():
            for pk_a, start_a, end_a in entries:
                if pk_a not in subset_pks:
                    continue
                for pk_b, start_b, end_b in entries:
                    if pk_b == pk_a:
                        continue
                    if is_overlap(start_a, end_a, start_b, end_b):
                        room_overlap_ids.add(pk_a)
                        break
        for speaker_pk, entries in by_speaker.items():
            for pk_a, start_a, end_a in entries:
                if pk_a not in subset_pks:
                    continue
                for pk_b, start_b, end_b in entries:
                    if pk_b == pk_a:
                        continue
                    if is_overlap(start_a, end_a, start_b, end_b):
                        speaker_overlaps_by_talk[pk_a].add(speaker_pk)
                        break
        return room_overlap_ids, speaker_overlaps_by_talk

    @cached_property
    def warnings(self) -> dict:
        """A dictionary of warnings to be acknowledged before a release.

        ``talk_warnings`` contains a list of talk-related warnings.
        ``unscheduled`` is the list of talks without a scheduled slot,
        ``unconfirmed`` is the list of submissions that will not be
        visible due to their unconfirmed status, and ``no_track`` are
        submissions without a track in a conference that uses tracks.
        """

        talks = self.talks.filter(submission__isnull=False)
        warnings = {
            'talk_warnings': [{'talk': key, 'warnings': value} for key, value in self.get_all_talk_warnings().items()],
            'unscheduled': talks.filter(start__isnull=True).count(),
            'unconfirmed': talks.exclude(submission__state=SubmissionStates.CONFIRMED).count(),
            'no_track': [],
        }
        if self.event.get_feature_flag('use_tracks'):
            warnings['no_track'] = talks.filter(submission__track_id__isnull=True)
        return warnings

    @cached_property
    def speakers_concerned(self):
        """Returns a dictionary of speakers with their new and changed talks in
        this schedule.

        Each speaker is assigned a dictionary with ``create`` and
        ``update`` fields, each containing a list of submissions.
        """
        result = {}
        if self.changes['action'] == 'create':
            for speaker in User.objects.filter(submissions__slots__schedule=self):
                talks = self.talks.filter(
                    submission__speakers=speaker,
                    room__isnull=False,
                    start__isnull=False,
                )
                if talks:
                    result[speaker] = {'create': talks, 'update': []}
            return result

        if self.changes['count'] == len(self.changes['canceled_talks']):
            return result

        speakers = {}
        for new_talk in self.changes['new_talks']:
            for speaker in new_talk.submission.speakers.all():
                speakers.setdefault(speaker, {'create': [], 'update': []})['create'].append(new_talk)
        for moved_talk in self.changes['moved_talks']:
            for speaker in moved_talk['submission'].speakers.all():
                speakers.setdefault(speaker, {'create': [], 'update': []})['update'].append(moved_talk)
        return speakers

    def generate_notifications(self, save=False):
        """A list of unsaved :class:`~pretalx.mail.models.QueuedMail` objects
        to be sent on schedule release."""

        mails = []
        for speaker, data in self.speakers_concerned.items():
            locale = speaker.get_locale_for_event(self.event)
            notifications = render_notifications(data, event=self.event, speaker=speaker, locale=locale)
            slots = list(data.get('create') or []) + [talk['new_slot'] for talk in (data.get('update') or [])]
            submissions = [slot.submission for slot in slots]
            mails.append(
                self.event.get_mail_template(MailTemplateRoles.NEW_SCHEDULE).to_mail(
                    user=speaker,
                    event=self.event,
                    context_kwargs={'user': speaker},
                    context={'notifications': notifications},
                    commit=save,
                    locale=locale,
                    submissions=submissions,
                    attachments=[
                        {
                            'name': f'{slot.frab_slug}.ics',
                            'content': slot.full_ical().serialize(),
                            'content_type': 'text/calendar',
                        }
                        for slot in slots
                    ],
                )
            )
        return mails

    generate_notifications.alters_data = True

    @cached_property
    def version_with_fallback(self):
        return self.version or 'wip'

    @cached_property
    def url_version(self):
        return quote(self.version_with_fallback)

    @cached_property
    def is_archived(self):
        if not self.version:
            return False

        return self != self.event.current_schedule

    def build_data(
        self,
        all_talks=False,
        filter_updated=None,
        all_rooms=False,
        enrich=False,
        *,
        submission_codes=None,
        include_featured_speaker_metadata=True,
        include_qrcodes=False,
        respect_public_visibility=True,
    ):
        """Build schedule JSON for widgets and exports.

        ``include_featured_speaker_metadata``: when False, clears ``is_featured`` and
        ``featured_position`` on each speaker so clients respect org "show featured sessions"
        without duplicating that logic in the frontend.

        ``respect_public_visibility``: when False, keeps organizer-only field data.

        ``submission_codes``: optional collection of submission codes; when given, only those
        talks are included.  Useful for building per-talk or per-speaker slim payloads.
        """
        talks = self.talks.all()
        if not all_talks:
            talks = self.talks.filter(is_visible=True)
        if respect_public_visibility:
            talks = talks.filter(room__isnull=False).exclude(room__deleted=True)
        if filter_updated:
            talks = talks.filter(updated__gte=filter_updated)
        if submission_codes is not None:
            talks = talks.filter(submission__code__in=submission_codes)
        talks = talks.select_related(
            'submission',
            'room',
            'submission__track',
            'submission__event',
            'submission__submission_type',
        ).prefetch_related('submission__speakers')
        if enrich:
            talks = talks.prefetch_related(
                'submission__resources',
                'submission__answers',
                'submission__answers__question',
                'submission__answers__options',
            )
        talks = talks.order_by('start')

        popularity_enabled = bool(self.event.feature_flags.get('session_popularity_enabled', False))
        show_content_locale = not respect_public_visibility or self.event.cfp.public_content_locale

        talk_list = list(talks)
        fav_counts: dict[str, int] = {}
        if popularity_enabled:
            visible_codes = [t.submission.code for t in talk_list if t.submission]
            if visible_codes:
                with scope(event=self.event):
                    fav_counts = {
                        row['submission__code']: row['count']
                        for row in SubmissionFavourite.objects.filter(
                            submission__event=self.event,
                            submission__code__in=visible_codes,
                        )
                        .values('submission__code')
                        .annotate(count=Count('id'))
                    }
        # Pre-fetch all stream schedules for this event's rooms.
        # Attach stream URL if a stream schedule overlaps this talk's time and room.
        with scope(event=self.event):
            stream_schedules = (
                StreamSchedule.objects.filter(
                    room__event=self.event,
                )
                .select_related('room')
                .only('room_id', 'start_time', 'end_time', 'url', 'stream_type')
                .order_by('start_time')
            )
        # Pre-normalize stream schedule times to UTC once so the per-talk
        # overlap check avoids repeated timezone conversions.
        stream_schedules_by_room = defaultdict(list)
        for ss in stream_schedules:
            if not (ss.room_id and ss.start_time and ss.end_time):
                continue
            ss_start = ss.start_time
            ss_end = ss.end_time
            if timezone.is_naive(ss_start):
                ss_start = timezone.make_aware(ss_start, timezone.get_current_timezone())
            if timezone.is_naive(ss_end):
                ss_end = timezone.make_aware(ss_end, timezone.get_current_timezone())
            stream_schedules_by_room[ss.room_id].append(
                (
                    ss_start.astimezone(UTC),
                    ss_end.astimezone(UTC),
                    ss,
                )
            )
        rooms: set[Room] = set(self.event.rooms.filter(deleted=False, is_unscheduled=False)) if all_rooms else set()
        tracks: set[Track] = set()
        speakers: set[User] = set()
        result = {
            'talks': [],
            'version': self.version,
            'timezone': self.event.timezone,
            'event_start': self.event.date_from.isoformat(),
            'event_end': self.event.date_to.isoformat(),
            'content_locales': self.event.content_locales if show_content_locale else [],
            'feature_flags': self.event.schedule_client_feature_flags(),
        }
        show_do_not_record = self.event.cfp.request_do_not_record
        show_abstract = self.event.cfp.public_abstract
        show_description = self.event.cfp.public_description
        show_slides = self.event.cfp.public_slides
        show_biography = self.event.cfp.public_biography
        base_url = str(self.event.urls.base)
        full_base_url = str(self.event.urls.base.full())
        # Resolve recording providers once; providers are event-level, not per-talk.
        recording_providers = []
        if enrich:
            for __, response in register_recording_provider.send_robust(self.event):
                if response and not isinstance(response, Exception) and getattr(response, 'get_recording', None):
                    recording_providers.append(response)
        for talk in talk_list:
            # Only add room if it's not deleted and not unscheduled
            if talk.room and not talk.room.deleted and not talk.room.is_unscheduled:
                rooms.add(talk.room)
            if talk.submission:
                tracks.add(talk.submission.track)
                talk_speakers = list(talk.submission.speakers.all())
                speakers.update(talk_speakers)
                talk_data = {
                    'code': talk.submission.code,
                    'id': talk.id,
                    'title': talk.submission.title,
                    'abstract': talk.submission.abstract if show_abstract else '',
                    'description': talk.submission.description if show_description else '',
                    'speakers': [speaker.code for speaker in talk_speakers],
                    'track': talk.submission.track_id if talk.submission else None,
                    'start': talk.local_start,
                    'end': talk.local_end,
                    'room': talk.room_id,
                    'duration': talk.submission.get_duration(),
                    'updated': talk.updated.isoformat(),
                    'state': talk.submission.state if all_talks else None,
                    'fav_count': (
                        fav_counts.get(talk.submission.code, 0) if (popularity_enabled and talk.submission) else 0
                    ),
                    'do_not_record': (talk.submission.do_not_record if show_do_not_record else None),
                    'tags': talk.submission.get_tag(),
                    'session_type': talk.submission.submission_type.name,
                    'content_locale': talk.submission.content_locale if show_content_locale else '',
                }
                # Attach stream URL if a stream schedule overlaps this slot.
                if talk.room_id and talk.start and talk.end:
                    schedules = stream_schedules_by_room.get(talk.room_id)
                    if schedules:
                        slot_start = talk.start
                        slot_end = talk.end
                        if timezone.is_naive(slot_start):
                            slot_start = timezone.make_aware(slot_start, timezone.get_current_timezone())
                        if timezone.is_naive(slot_end):
                            slot_end = timezone.make_aware(slot_end, timezone.get_current_timezone())
                        slot_start = slot_start.astimezone(UTC)
                        slot_end = slot_end.astimezone(UTC)

                        match = None
                        for ss_start, ss_end, ss in schedules:
                            if ss_start < slot_end and ss_end > slot_start:
                                match = ss
                                break
                        if match:
                            talk_data['stream_url'] = match.url
                            talk_data['stream_type'] = match.stream_type
                if enrich:
                    talk_data['resources'] = [
                        enriched_resource_entry(resource)
                        for resource in talk.submission.resources.all()
                        if resource.url and (show_slides or resource.kind != 'slides')
                    ]
                    talk_data['answers'] = [
                        {
                            'question': str(answer.question.question),
                            'answer': str(answer.answer_string),
                            'question_id': answer.question_id,
                            'options': [str(opt.answer) for opt in answer.options.all()],
                        }
                        for answer in talk.submission.answers.all()
                        if answer.question and answer.question.is_public
                    ]
                    # Per-talk export URLs
                    code = talk.submission.code
                    ics_url = f'{base_url}talk/{code}.ics'
                    google_url = f'{base_url}talk/{code}/export/google-calendar'
                    webcal_url = f'{base_url}talk/{code}/export/webcal'
                    talk_data['exporters'] = {
                        'ics': ics_url,
                        'json': f'{base_url}talk/{code}.json',
                        'xml': f'{base_url}talk/{code}.xml',
                        'xcal': f'{base_url}talk/{code}.xcal',
                        'google_calendar': google_url,
                        'webcal': webcal_url,
                    }
                    if include_qrcodes:
                        talk_data['exporters']['qrcodes'] = make_talk_qr_map(full_base_url, code)
                    # Recording iframe from provider plugins
                    recording_iframe = ''
                    for provider in recording_providers:
                        rec = provider.get_recording(talk.submission)
                        if rec and rec.get('iframe'):
                            recording_iframe = rec['iframe']
                            break
                    talk_data['recording_iframe'] = recording_iframe
                result['talks'].append(talk_data)
            else:
                result['talks'].append(
                    {
                        'id': talk.id,
                        'title': talk.description,
                        'start': talk.start,
                        'end': talk.local_end,
                        'room': talk.room_id,
                    }
                )
        tracks.discard(None)
        tracks = sorted(tracks, key=lambda track: track.position or 0)
        result['tracks'] = [
            {
                'id': track.id,
                'name': track.name,
                'description': track.description,
                'color': track.color,
            }
            for track in tracks
        ]
        result['rooms'] = [
            {
                'id': room.id,
                'name': room.name,
                'description': room.description if room.description else '',
                'video_url': getattr(room, 'video_url', ''),
                'has_interpretation': room.has_interpretation,
            }
            for room in sorted(rooms, key=lambda r: (r.position if r.position is not None else 9999, r.id))
        ]

        include_avatar = self.event.cfp.request_avatar and self.event.cfp.public_avatar
        speaker_list = []
        # Prefetch all speaker profiles for this event to avoid N+1 queries

        speaker_profiles = {
            profile.user_id: profile
            for profile in SpeakerProfile.objects.filter(
                event=self.event,
                user__in=speakers,
            ).select_related('user')
        }
        for user in speakers:
            # Avoid calling event_profile() here: it can hit the DB (and even create/save
            # a profile). For schedule JSON, missing profiles should simply result in
            # empty optional fields.
            profile = speaker_profiles.get(user.pk)
            speaker_data = {
                'code': user.code,
                'name': user.fullname or None,
                'biography': getattr(profile, 'biography', '') if show_biography else '',
                'avatar': (user.get_avatar_url(event=self.event) if include_avatar else None),
                'avatar_thumbnail_default': (
                    user.get_avatar_url(event=self.event, thumbnail='default') if include_avatar else None
                ),
                'avatar_thumbnail_tiny': (
                    user.get_avatar_url(event=self.event, thumbnail='tiny') if include_avatar else None
                ),
                'is_featured': bool(getattr(profile, 'is_featured', False)),
                'featured_position': getattr(profile, 'position', None),
            }
            if not include_featured_speaker_metadata:
                speaker_data['is_featured'] = False
                speaker_data['featured_position'] = None
            if enrich:
                spk_base = f'{base_url}speakers/{user.code}'
                spk_full_base = f'{full_base_url}speakers/{user.code}'
                spk_ics = f'{spk_base}/talks.ics'
                spk_google = f'{spk_base}/talks/export/google-calendar'
                spk_webcal = f'{spk_base}/talks/export/webcal'
                speaker_data['exporters'] = {
                    'ics': spk_ics,
                    'json': f'{spk_base}/talks.json',
                    'xml': f'{spk_base}/talks.xml',
                    'xcal': f'{spk_base}/talks.xcal',
                    'google_calendar': spk_google,
                    'webcal': spk_webcal,
                }
                if include_qrcodes:
                    speaker_data['exporters']['qrcodes'] = make_speaker_qr_map(spk_full_base)
            speaker_list.append(speaker_data)
        result['speakers'] = speaker_list
        return result

    def __str__(self) -> str:
        """Help when debugging."""
        return f'Schedule(event={self.event.slug}, version={self.version})'


def count_fav_talk(submission_code):
    count = SubmissionFavourite.objects.filter(submission__code=submission_code).aggregate(count=Count('id'))['count']
    return count
