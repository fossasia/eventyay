"""Redis/cache keys and timeouts for two separate caches:

* **Released schedule JSON** — ``Schedule.build_data()`` output for a versioned schedule.
* **Video page HTML** — anonymous ``/…/video/`` HTML shell (includes host-specific websocket URL).

Each has its own key helpers and expiry (Django ``cache.set(..., timeout=…)`` uses seconds).

Stale-while-revalidate
----------------------
Every successful ``build_data()`` call also writes a *stale* copy under
``schedule_json_stale_cache_key()``.  The stale key has no stamp component
so it survives ``invalidate_build_data_cache()`` intact.  On a fresh-cache
miss the view returns the stale payload immediately and enqueues a Celery
rebuild, ensuring no user ever waits for recomputation.
"""

import random
from datetime import timedelta

# Base lifetimes before ±15 min jitter is applied in *_timeout_secs().
SCHEDULE_JSON_CACHE_LIFETIME = timedelta(hours=1)
SCHEDULE_JSON_STALE_CACHE_LIFETIME = timedelta(hours=24)
VIDEO_HTML_CACHE_LIFETIME = timedelta(hours=1)
FAVOURITE_FLUSH_THROTTLE = timedelta(minutes=30)


def schedule_json_stamp_key(schedule_pk: int) -> str:
    """Redis key for the stamp that busts cached ``build_data()`` JSON for this schedule."""
    return f'schedule_build_data_stamp_{schedule_pk}'


def schedule_json_cache_key(
    schedule_pk: int,
    all_talks: bool,
    enrich: bool,
    include_featured_speaker_metadata: bool,
    include_qr_codes: bool,
    language: str,
    stamp: int,
) -> str:
    """Redis key for one cached ``build_data()`` payload (language + stamp disambiguate variants)."""
    return (
        f'schedule_build_data_{schedule_pk}'
        f'_at{int(all_talks)}_e{int(enrich)}_fs{int(include_featured_speaker_metadata)}'
        f'_qr{int(include_qr_codes)}_{language}_v{stamp}'
    )


def schedule_json_stale_cache_key(
    schedule_pk: int,
    all_talks: bool,
    enrich: bool,
    include_featured_speaker_metadata: bool,
    include_qr_codes: bool,
    language: str,
) -> str:
    """Redis key for the last-known-good ``build_data()`` payload (no stamp — survives invalidation).

    Used by stale-while-revalidate: returned instantly on a fresh-cache miss while
    the Celery rebuild task recomputes in the background.
    """
    return (
        f'schedule_build_data_stale_{schedule_pk}'
        f'_at{int(all_talks)}_e{int(enrich)}_fs{int(include_featured_speaker_metadata)}'
        f'_qr{int(include_qr_codes)}_{language}'
    )


def video_html_stamp_key(event_id: int, schedule_version: str) -> str:
    """Redis key for the stamp that busts cached video SPA HTML for this event/version."""
    return f'video_spa_html_stamp_{event_id}_{schedule_version}'


def video_html_cache_key(
    event_id: int,
    schedule_version: str,
    language: str,
    scheme: str,
    host: str,
    stamp: int | float,
) -> str:
    """Redis key for one cached anonymous video SPA HTML response."""
    return f'video_spa_html_{event_id}_{schedule_version}_{language}_{scheme}_{host}_{stamp}'


def schedule_json_cache_timeout_secs() -> int:
    """Seconds until a cached ``build_data()`` JSON entry expires (1 h ± 15 min, floored at 60 s)."""
    return max(60, int(SCHEDULE_JSON_CACHE_LIFETIME.total_seconds()) + random.randint(-900, 900))


def video_html_cache_timeout_secs() -> int:
    """Seconds until a cached video SPA HTML entry expires (1 h ± 15 min, floored at 60 s)."""
    return max(60, int(VIDEO_HTML_CACHE_LIFETIME.total_seconds()) + random.randint(-900, 900))
