"""Cache key builders and expiry helpers for two caches:

- Released schedule JSON produced by ``Schedule.build_data()``.
- Anonymous video page HTML served by ``VideoSPAView``.

Serve-stale-while-rebuilding
----------------------------
Every ``build_data()`` write also stores a long-lived backup under
``schedule_json_backup_key()``.  The backup key has no stamp in it so it
survives invalidation.  When the main entry is missing (e.g. after an edit
bumped the stamp), the view serves the backup instantly and queues a
background rebuild — no visitor waits for a full recompute.
"""

import random


_schedule_json_expire_min = 24 * 3600
_schedule_json_expire_max = 48 * 3600

_video_html_expire_min = 24 * 3600
_video_html_expire_max = 48 * 3600

_schedule_json_backup_expire = 72 * 3600

_star_flush_base = 60 * 60
_star_flush_spread = 15 * 60


def schedule_json_stamp_key(schedule_pk: int) -> str:
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
    return (
        f'schedule_build_data_{schedule_pk}'
        f'_at{int(all_talks)}_e{int(enrich)}_fs{int(include_featured_speaker_metadata)}'
        f'_qr{int(include_qr_codes)}_{language}_v{stamp}'
    )


def schedule_json_backup_key(
    schedule_pk: int,
    all_talks: bool,
    enrich: bool,
    include_featured_speaker_metadata: bool,
    include_qr_codes: bool,
    language: str,
) -> str:
    """Key for the last-known-good schedule JSON that survives stamp invalidation."""
    return (
        f'schedule_build_data_stale_{schedule_pk}'
        f'_at{int(all_talks)}_e{int(enrich)}_fs{int(include_featured_speaker_metadata)}'
        f'_qr{int(include_qr_codes)}_{language}'
    )


def video_html_stamp_key(event_id: int, schedule_version: str) -> str:
    return f'video_spa_html_stamp_{event_id}_{schedule_version}'


def video_html_cache_key(
    event_id: int,
    schedule_version: str,
    language: str,
    scheme: str,
    host: str,
    stamp: int | float,
) -> str:
    return f'video_spa_html_{event_id}_{schedule_version}_{language}_{scheme}_{host}_{stamp}'


def schedule_json_expire_seconds() -> int:
    """Random expiry between 24 h and 48 h so Redis entries naturally spread their refresh times."""
    return random.randint(_schedule_json_expire_min, _schedule_json_expire_max)


def schedule_json_backup_expire_seconds() -> int:
    """Expiry for the backup entry — always longer than the longest main expiry (48 h)."""
    return _schedule_json_backup_expire


def video_html_expire_seconds() -> int:
    """Random expiry between 24 h and 48 h for the cached anonymous video page HTML."""
    return random.randint(_video_html_expire_min, _video_html_expire_max)


def star_flush_delay_seconds() -> int:
    """How long to block further star-count-driven cache flushes for one event (1 h ± 15 min)."""
    return max(60, _star_flush_base + random.randint(-_star_flush_spread, _star_flush_spread))
