"""Convert public video-link answers into embeddable iframe URLs and CSP origins."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse

_YOUTUBE_HOSTS = frozenset(
    {
        'youtube.com',
        'www.youtube.com',
        'm.youtube.com',
        'youtu.be',
        'www.youtu.be',
        'youtube-nocookie.com',
        'www.youtube-nocookie.com',
    }
)
_VIMEO_HOSTS = frozenset({'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'})
_TIME_COMPONENT_RE = re.compile(r'^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$')


def _parse_time_to_seconds(value: str | None) -> int | None:
    """Parse YouTube/Vimeo time values (``90``, ``1m30s``, ``1h2m3s``) into seconds."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    match = _TIME_COMPONENT_RE.fullmatch(raw)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _fragment_time_value(fragment: str | None) -> str | None:
    if not fragment:
        return None
    if fragment.startswith('t='):
        return fragment[2:]
    return None


def _youtube_id(parsed) -> str | None:
    host = (parsed.hostname or '').lower()
    path = parsed.path or ''
    if host in ('youtu.be', 'www.youtu.be'):
        video_id = path.strip('/').split('/', 1)[0]
        return video_id or None
    if host not in _YOUTUBE_HOSTS:
        return None
    parts = [part for part in path.split('/') if part]
    if not parts:
        return None
    if parts[0] in ('embed', 'shorts', 'live', 'v') and len(parts) >= 2:
        return parts[1]
    if parts[0] == 'watch':
        return (parse_qs(parsed.query).get('v') or [None])[0]
    return (parse_qs(parsed.query).get('v') or [None])[0]


def _youtube_start_seconds(parsed) -> int | None:
    query = parse_qs(parsed.query)
    for key in ('start', 't'):
        values = query.get(key) or []
        if values:
            seconds = _parse_time_to_seconds(values[0])
            if seconds is not None and seconds > 0:
                return seconds
    fragment_time = _fragment_time_value(parsed.fragment)
    if fragment_time:
        seconds = _parse_time_to_seconds(fragment_time)
        if seconds is not None and seconds > 0:
            return seconds
    return None


def _vimeo_id(parsed) -> str | None:
    host = (parsed.hostname or '').lower()
    if host not in _VIMEO_HOSTS:
        return None
    parts = [part for part in (parsed.path or '').split('/') if part]
    if host == 'player.vimeo.com':
        if len(parts) >= 2 and parts[0] == 'video':
            return parts[1]
        return None
    for part in reversed(parts):
        if part.isdigit():
            return part
    return None


def _vimeo_time_hash(parsed) -> str | None:
    """Return a Vimeo ``#t=…`` fragment, preserving the original format when possible."""
    fragment_time = _fragment_time_value(parsed.fragment)
    if fragment_time:
        # Keep provider-native fragment text when valid (e.g. 1m30s)
        if _parse_time_to_seconds(fragment_time) is not None:
            return f't={fragment_time}'
    query = parse_qs(parsed.query)
    for key in ('t', 'time'):
        values = query.get(key) or []
        if not values:
            continue
        seconds = _parse_time_to_seconds(values[0])
        if seconds is not None and seconds > 0:
            return f't={seconds}s'
    return None


def _youtube_embed_url(video_id: str, parsed) -> str:
    params = {'autoplay': '0'}
    start = _youtube_start_seconds(parsed)
    if start:
        params['start'] = str(start)
    return f'https://www.youtube-nocookie.com/embed/{video_id}?{urlencode(params)}'


def _vimeo_embed_url(video_id: str, parsed) -> str:
    # autoplay=0 keeps the player paused on load; timestamps use the #t= fragment.
    embed_url = f'https://player.vimeo.com/video/{video_id}?{urlencode({"autoplay": "0"})}'
    time_hash = _vimeo_time_hash(parsed)
    if time_hash:
        embed_url = f'{embed_url}#{time_hash}'
    return embed_url


def get_video_embed_info(url: str | None) -> dict[str, object] | None:
    """Return embed URL and CSP frame-src origins for a video-link field answer.

    Only YouTube and Vimeo URLs are converted to embeds. Timestamps are preserved
    and autoplay is always disabled. Regular URL custom fields are never passed
    here; arbitrary HTTPS pages are not treated as embeddable players.
    """
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None

    youtube_id = _youtube_id(parsed)
    if youtube_id:
        return {
            'embed_url': _youtube_embed_url(youtube_id, parsed),
            'csp_origins': ['https://www.youtube-nocookie.com', 'https://www.youtube.com'],
            'provider': 'youtube',
        }

    vimeo_id = _vimeo_id(parsed)
    if vimeo_id:
        return {
            'embed_url': _vimeo_embed_url(vimeo_id, parsed),
            'csp_origins': ['https://player.vimeo.com'],
            'provider': 'vimeo',
        }

    return None
