"""
Tests for released schedule JSON cache (``Schedule.build_data()``) and invalidation signals.
"""
import pytest
from django.core.cache import cache
from django_scopes import scope

from eventyay.base.cache_keys import (
    FAVOURITE_FLUSH_THROTTLE,
    SCHEDULE_JSON_CACHE_LIFETIME,
    schedule_json_cache_key,
    schedule_json_cache_timeout_secs,
    schedule_json_stamp_key,
    video_html_cache_timeout_secs,
    video_html_stamp_key,
)


class TestCacheKeys:
    def test_schedule_json_stamp_key_is_consistent(self):
        assert schedule_json_stamp_key(42) == schedule_json_stamp_key(42)

    def test_schedule_json_stamp_key_varies_by_pk(self):
        assert schedule_json_stamp_key(1) != schedule_json_stamp_key(2)

    def test_video_html_stamp_key_includes_event_and_version(self):
        key = video_html_stamp_key(7, 'v1.0')
        assert '7' in key
        assert 'v1.0' in key

    def test_schedule_json_cache_lifetime_is_positive(self):
        assert SCHEDULE_JSON_CACHE_LIFETIME.total_seconds() > 0

    def test_cache_timeouts_never_below_sixty_seconds(self):
        for _ in range(30):
            assert schedule_json_cache_timeout_secs() >= 60
            assert video_html_cache_timeout_secs() >= 60

    def test_favourite_flush_throttle_is_positive(self):
        assert FAVOURITE_FLUSH_THROTTLE.total_seconds() > 0


@pytest.mark.django_db
class TestBuildDataCacheHitMiss:
    """Verify that versioned schedules are cached and WIP schedules are not."""

    @pytest.fixture
    def schedule_with_version(self, event):
        from eventyay.base.models.schedule import Schedule

        with scope(event=event):
            sched = Schedule.objects.create(event=event, version='v1')
        return sched

    def test_versioned_schedule_writes_cache_entry(self, schedule_with_version):
        """First call stores the result in cache under the expected key."""
        sched = schedule_with_version
        cache.clear()
        with scope(event=sched.event):
            sched.build_data()
        stamp = cache.get(schedule_json_stamp_key(sched.pk), 0)
        expected_key = schedule_json_cache_key(sched.pk, False, False, True, True, 'en', stamp)
        assert cache.get(expected_key) is not None, 'build_data result must be stored under the expected cache key'

    def test_versioned_schedule_uses_cached_result(self, schedule_with_version):
        """Second call returns the cached value without hitting the DB again."""
        sched = schedule_with_version
        cache.clear()
        with scope(event=sched.event):
            result1 = sched.build_data()
            result2 = sched.build_data()
        assert result1 == result2

    def test_wip_schedule_is_not_cached(self, event):
        from eventyay.base.models.schedule import Schedule

        with scope(event=event):
            wip = Schedule.objects.create(event=event)
        cache.clear()
        with scope(event=wip.event):
            wip.build_data()
        assert cache.get(schedule_json_stamp_key(wip.pk)) is None, 'WIP schedule must not write a stamp'

    def test_invalidate_bumps_stamp(self, schedule_with_version):
        sched = schedule_with_version
        cache.clear()
        old_stamp = cache.get(schedule_json_stamp_key(sched.pk), 0)
        sched.invalidate_build_data_cache()
        new_stamp = cache.get(schedule_json_stamp_key(sched.pk))
        assert new_stamp is not None
        assert new_stamp != old_stamp, 'Stamp must change after invalidation'

    def test_invalidate_makes_old_cache_key_unreachable(self, schedule_with_version):
        """After invalidation the old cache entry is unreachable via the new stamp."""
        sched = schedule_with_version
        cache.clear()
        with scope(event=sched.event):
            sched.build_data()
        stamp_before = cache.get(schedule_json_stamp_key(sched.pk), 0)
        old_key = schedule_json_cache_key(sched.pk, False, False, True, True, 'en', stamp_before)
        assert cache.get(old_key) is not None, 'Entry must be cached before invalidation'

        sched.invalidate_build_data_cache()

        stamp_after = cache.get(schedule_json_stamp_key(sched.pk))
        assert stamp_after != stamp_before, 'Stamp must change'
        assert cache.get(old_key) is not None, 'Old entry still in Redis (expires via TTL)'
        new_key = schedule_json_cache_key(sched.pk, False, False, True, True, 'en', stamp_after)
        assert new_key != old_key, 'New key must differ — next build_data call will miss and recompute'


@pytest.mark.django_db
class TestScheduleCacheSignals:
    """Verify that signal handlers invalidate the build_data cache."""

    @pytest.fixture
    def released_schedule(self, event):
        from eventyay.base.models.schedule import Schedule

        with scope(event=event):
            sched = Schedule.objects.create(event=event, version='v1')
        return sched

    def test_event_save_bumps_stamp(self, released_schedule):
        sched = released_schedule
        cache.clear()
        old_stamp = cache.get(schedule_json_stamp_key(sched.pk), 0)

        with scope(event=sched.event):
            sched.event.save()

        new_stamp = cache.get(schedule_json_stamp_key(sched.pk))
        assert new_stamp is not None
        assert new_stamp != old_stamp, 'Event save should bump the schedule JSON stamp'

    def test_invalidate_build_data_cache_method(self, released_schedule):
        sched = released_schedule
        cache.clear()
        with scope(event=sched.event):
            sched.build_data()
        sched.invalidate_build_data_cache()
        new_stamp = cache.get(schedule_json_stamp_key(sched.pk))
        assert new_stamp is not None, 'Stamp must be set after invalidation'
