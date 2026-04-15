import time

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_scopes import scopes_disabled

from eventyay.base.models.cfp import CfP
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.question import Answer, AnswerOption, TalkQuestion
from eventyay.base.models.resource import Resource
from eventyay.base.models.room import Room
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.models.submission import Submission, SubmissionFavourite
from eventyay.base.models.track import Track

FAVOURITE_FLUSH_THROTTLE_SECONDS = 30 * 60


def _bump_stamp(event_id, version):
    cache.set(f'video_spa_html_stamp_{event_id}_{version or "none"}', time.time(), timeout=None)


def _invalidate_schedules(schedules):
    for schedule in schedules:
        schedule.invalidate_build_data_cache()
        _bump_stamp(schedule.event_id, schedule.version)


def _versioned_schedules_for_event(event_id):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        return list(
            Schedule.objects.filter(event_id=event_id, version__isnull=False).only(
                'pk', 'event_id', 'version'
            )
        )


@receiver(post_save, sender=TalkSlot, dispatch_uid='schedule_cache_talkslot_save')
@receiver(post_delete, sender=TalkSlot, dispatch_uid='schedule_cache_talkslot_delete')
def invalidate_on_talkslot_change(sender, instance, **kwargs):
    with scopes_disabled():
        schedule = instance.schedule
        if schedule.version:
            schedule.invalidate_build_data_cache()
            _bump_stamp(schedule.event_id, schedule.version)


@receiver(post_save, sender=Submission, dispatch_uid='schedule_cache_submission_save')
def invalidate_on_submission_change(sender, instance, **kwargs):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission=instance, version__isnull=False)
            .distinct()
            .only('pk', 'event_id', 'version')
        )
    _invalidate_schedules(schedules)


@receiver(post_save, sender=Resource, dispatch_uid='schedule_cache_resource_save')
@receiver(post_delete, sender=Resource, dispatch_uid='schedule_cache_resource_delete')
def invalidate_on_resource_change(sender, instance, **kwargs):
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission=instance.submission, version__isnull=False)
            .distinct()
            .only('pk', 'event_id', 'version')
        )
    _invalidate_schedules(schedules)


@receiver(post_save, sender=Answer, dispatch_uid='schedule_cache_answer_save')
@receiver(post_delete, sender=Answer, dispatch_uid='schedule_cache_answer_delete')
def invalidate_on_answer_change(sender, instance, **kwargs):
    if not instance.submission_id:
        return
    from eventyay.base.models.schedule import Schedule  # local import: circular dependency

    with scopes_disabled():
        schedules = list(
            Schedule.objects.filter(talks__submission_id=instance.submission_id, version__isnull=False)
            .distinct()
            .only('pk', 'event_id', 'version')
        )
    _invalidate_schedules(schedules)


@receiver(post_save, sender=AnswerOption, dispatch_uid='schedule_cache_answeroption_save')
@receiver(post_delete, sender=AnswerOption, dispatch_uid='schedule_cache_answeroption_delete')
def invalidate_on_answeroption_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.question.event_id))


@receiver(post_save, sender=TalkQuestion, dispatch_uid='schedule_cache_talkquestion_save')
def invalidate_on_talkquestion_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.event_id))


@receiver(post_save, sender=SpeakerProfile, dispatch_uid='schedule_cache_speakerprofile_save')
def invalidate_on_speakerprofile_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.event_id))


@receiver(post_save, sender=Room, dispatch_uid='schedule_cache_room_save')
def invalidate_on_room_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.event_id))


@receiver(post_save, sender=Track, dispatch_uid='schedule_cache_track_save')
def invalidate_on_track_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.event_id))


@receiver(post_save, sender=StreamSchedule, dispatch_uid='schedule_cache_streamschedule_save')
@receiver(post_delete, sender=StreamSchedule, dispatch_uid='schedule_cache_streamschedule_delete')
def invalidate_on_streamschedule_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.room.event_id))


@receiver(post_save, sender='base.Event', dispatch_uid='schedule_cache_event_save')
def invalidate_on_event_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.pk))


@receiver(post_save, sender=CfP, dispatch_uid='schedule_cache_cfp_save')
def invalidate_on_cfp_change(sender, instance, **kwargs):
    _invalidate_schedules(_versioned_schedules_for_event(instance.event_id))


@receiver(post_save, sender='base.User', dispatch_uid='schedule_cache_user_save')
def invalidate_on_user_change(sender, instance, **kwargs):
    with scopes_disabled():
        event_ids = list(
            SpeakerProfile.objects.filter(user=instance)
            .values_list('event_id', flat=True)
            .distinct()
        )
    for event_id in event_ids:
        _invalidate_schedules(_versioned_schedules_for_event(event_id))


@receiver(post_save, sender=SubmissionFavourite, dispatch_uid='schedule_cache_submissionfavourite_save')
@receiver(post_delete, sender=SubmissionFavourite, dispatch_uid='schedule_cache_submissionfavourite_delete')
def invalidate_on_submissionfavourite_change(sender, instance, **kwargs):
    with scopes_disabled():
        event_id = instance.submission.event_id
    throttle_key = f'schedule_fav_flush_throttle_{event_id}'
    if not cache.add(throttle_key, 1, timeout=FAVOURITE_FLUSH_THROTTLE_SECONDS):
        return
    _invalidate_schedules(_versioned_schedules_for_event(event_id))
