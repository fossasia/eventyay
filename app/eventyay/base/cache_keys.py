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

TTL policy
----------
* **Fresh schedule / video HTML** — random **24–48 hours** per ``cache.set`` call.
  Edits still bump stamps immediately; this only limits how long unchanged
  data lives in Redis without a signal.
* **Stale schedule JSON** — **72 hours** so it always outlives the longest fresh TTL.
* **Submission favourite flush throttle** — **1 hour ± 15 minutes** (random per throttle window)
  so star counts refresh on that cadence without hammering the cache on every star.
"""

import random
from datetime import timedelta

# Fresh ``build_data`` / video HTML: random TTL in this inclusive second range.
SCHEDULE_JSON_CACHE_TTL_MIN_SEC = 24 * 3600
SCHEDULE_JSON_CACHE_TTL_MAX_SEC = 48 * 3600

VIDEO_HTML_CACHE_TTL_MIN_SEC = 24 * 3600
VIDEO_HTML_CACHE_TTL_MAX_SEC = 48 * 3600

# Stale schedule JSON must outlive the longest possible fresh TTL (48 h).
SCHEDULE_JSON_STALE_CACHE_LIFETIME = timedelta(hours=72)

# Favourite-driven invalidation: base 1 h, ±15 min jitter (seconds).
_FAVOURITE_FLUSH_BASE_SEC = 60 * 60
_FAVOURITE_FLUSH_JITTER_SEC = 15 * 60


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
    """Seconds until a cached ``build_data()`` JSON entry expires (24–48 h, uniform random)."""
    return random.randint(SCHEDULE_JSON_CACHE_TTL_MIN_SEC, SCHEDULE_JSON_CACHE_TTL_MAX_SEC)


def video_html_cache_timeout_secs() -> int:
    """Seconds until a cached video SPA HTML entry expires (24–48 h, uniform random)."""
    return random.randint(VIDEO_HTML_CACHE_TTL_MIN_SEC, VIDEO_HTML_CACHE_TTL_MAX_SEC)


def favourite_flush_throttle_timeout_secs() -> int:
    """Seconds until another favourite-driven schedule cache flush is allowed (1 h ± 15 min)."""
    return max(60, _FAVOURITE_FLUSH_BASE_SEC + random.randint(-_FAVOURITE_FLUSH_JITTER_SEC, _FAVOURITE_FLUSH_JITTER_SEC))
