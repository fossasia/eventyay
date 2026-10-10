import datetime as dt

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import transaction
from django.test.utils import override_settings
from django_scopes import scope

from eventyay.agenda.views.utils import get_or_build_landing_featured_widget_schedule
from eventyay.base.models import Room, Submission, SubmissionType, TalkSlot
from eventyay.base.services.stale_cache import get_schedule_cache_version

LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'schedule-speaker-roles-tests',
    }
}


@pytest.fixture
def schedule(event, user):
    """A released schedule with one session given by `user`, who has a job title and organization."""
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(
            title='Keynote', event=event, submission_type=submission_type, content_locale='en'
        )
        submission.speakers.add(user)
        submission.accept()
        submission.confirm()
        room = Room.objects.create(event=event, name='Main Hall')
        slot = {
            'is_visible': True,
            'start': event.date_from + dt.timedelta(hours=10),
            'end': event.date_from + dt.timedelta(hours=11),
            'room': room,
        }
        TalkSlot.objects.update_or_create(submission=submission, schedule=event.wip_schedule, defaults=slot)
        event.release_schedule('v1')
        TalkSlot.objects.update_or_create(submission=submission, schedule=event.current_schedule, defaults=slot)
        profile = user.event_profile(event)
        profile.job_title = 'Founder'
        profile.organization = 'FOSSASIA'
        profile.save()
        return event.current_schedule


def set_public(event, **public):
    """Mark CfP speaker fields as public or not, as on the CfP settings page."""
    for field, value in public.items():
        field_settings = dict(event.cfp.fields.get(field) or {})
        field_settings['public'] = value
        event.cfp.fields[field] = field_settings
    event.cfp.save()


def landing_speaker_role(event, user):
    """Return the speaker_role of `user` in the featured speaker cards on the event Info page."""
    with scope(event=event):
        data = get_or_build_landing_featured_widget_schedule(event, AnonymousUser())
    return next(speaker['speaker_role'] for speaker in data['speakers'] if speaker['code'] == user.code)


def compact_speaker_role(schedule, user):
    """Return the speaker_role of `user` in the compact schedule data used by the public schedule."""
    with scope(event=schedule.event):
        data = schedule.build_data(compact=True)
    return next(speaker['speaker_role'] for speaker in data['speakers'] if speaker['code'] == user.code)


@pytest.mark.django_db
def test_compact_schedule_includes_public_speaker_role(event, user, schedule):
    """The compact schedule data includes the job title and organization when both are public."""
    set_public(event, job_title=True, organization=True)

    assert compact_speaker_role(schedule, user) == 'Founder, FOSSASIA'


@pytest.mark.django_db
def test_compact_schedule_only_includes_public_role_fields(event, user, schedule):
    """Fields that are not public are left out of the speaker role."""
    set_public(event, job_title=False, organization=True)

    assert compact_speaker_role(schedule, user) == 'FOSSASIA'


@pytest.mark.django_db
def test_compact_schedule_speaker_role_is_empty_when_not_public(event, user, schedule):
    """Without public role fields, the speaker role is empty, so the schedule shows no label."""
    set_public(event, job_title=False, organization=False)

    assert compact_speaker_role(schedule, user) == ''


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_featured_speaker_cards_follow_role_visibility_changes(event, user, django_capture_on_commit_callbacks):
    """Making the role fields public refreshes the cached featured speaker cards on the Info page."""
    cache.clear()
    with django_capture_on_commit_callbacks(execute=True):
        event.feature_flags['show_featured_speakers'] = 'always'
        event.save()
        with scope(event=event):
            profile = user.event_profile(event)
            profile.job_title = 'Founder'
            profile.organization = 'FOSSASIA'
            profile.is_featured = True
            profile.save()
        set_public(event, job_title=False, organization=False)
    assert landing_speaker_role(event, user) == ''

    with django_capture_on_commit_callbacks(execute=True):
        set_public(event, job_title=True, organization=True)

    assert landing_speaker_role(event, user) == 'Founder, FOSSASIA'


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_rolled_back_change_does_not_stop_a_later_cache_refresh(event, django_capture_on_commit_callbacks):
    """A visibility change that is rolled back must not keep a later change from refreshing the caches."""
    cache.clear()
    version = get_schedule_cache_version(event.pk)
    with pytest.raises(RuntimeError), transaction.atomic():
        set_public(event, job_title=True, organization=True)
        raise RuntimeError

    with django_capture_on_commit_callbacks(execute=True):
        set_public(event, job_title=False, organization=False)

    assert get_schedule_cache_version(event.pk) == version + 1


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_cache_version_is_bumped_once_per_commit(event, django_capture_on_commit_callbacks):
    """Several changes in one transaction refresh the caches once."""
    cache.clear()
    version = get_schedule_cache_version(event.pk)

    with django_capture_on_commit_callbacks(execute=True):
        set_public(event, job_title=True)
        set_public(event, organization=True)

    assert get_schedule_cache_version(event.pk) == version + 1
