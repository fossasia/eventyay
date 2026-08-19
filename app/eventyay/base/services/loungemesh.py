from __future__ import annotations

from datetime import timedelta
import json
from typing import Any
from urllib.parse import urlencode, urlparse

import jwt
from django.apps import apps
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models.loungemesh import LoungeMeshAccessToken
from eventyay.base.settings import GlobalSettingsObject

LOUNGEMESH_MODULE_TYPE = 'call.loungemesh'
LOUNGEMESH_PLUGIN_MODULE = 'eventyay_loungemesh'
DEFAULT_LOUNGEMESH_URL = 'https://loungemesh.com'
TOKEN_TTL = timedelta(hours=2)

ORGANIZER_FEATURE_KEYS: tuple[str, ...] = (
    'notes',
    'whiteboard',
    'poll',
    'chat',
    'screenshare',
    'reactions',
    'lobby',
)

ROOM_DEFAULT_FEATURE_KEYS: tuple[str, ...] = (
    'notes',
    'whiteboard',
    'poll',
    'chat',
    'screenshare',
    'reactions',
    'lobby',
)


def default_organizer_features() -> list[str]:
    return list(ORGANIZER_FEATURE_KEYS)


def get_loungemesh_settings() -> dict[str, Any]:
    gs = GlobalSettingsObject().settings
    features = gs.get('loungemesh_organizer_features', default=default_organizer_features())
    if isinstance(features, str):
        try:
            features = json.loads(features)
        except json.JSONDecodeError:
            features = default_organizer_features()
    if not isinstance(features, list):
        features = default_organizer_features()
    allowed = [key for key in features if key in ORGANIZER_FEATURE_KEYS]
    return {
        'enabled': bool(gs.get('loungemesh_enabled', default=False)),
        'url': (gs.get('loungemesh_url', default=DEFAULT_LOUNGEMESH_URL) or DEFAULT_LOUNGEMESH_URL).rstrip('/'),
        'jitsi_app_id': gs.get('loungemesh_jitsi_app_id', default='') or '',
        'jitsi_app_secret': gs.get('loungemesh_jitsi_app_secret', default='') or '',
        'organizer_features': allowed,
    }


def origin_from_url(url: str) -> str | None:
    parsed = urlparse((url or '').strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None
    return f'{parsed.scheme}://{parsed.netloc}'


def loungemesh_embed_origins() -> tuple[str, ...]:
    settings = get_loungemesh_settings()
    origins: list[str] = []
    for url in (DEFAULT_LOUNGEMESH_URL, settings['url']):
        origin = origin_from_url(url)
        if origin and origin not in origins:
            origins.append(origin)
    return tuple(origins)


def loungemesh_permissions_policy() -> str:
    quoted = ' '.join(f'"{origin}"' for origin in loungemesh_embed_origins())
    allow = f'(self {quoted})' if quoted else '(self)'
    return (
        f'camera={allow}, microphone={allow}, display-capture={allow}, '
        f'fullscreen={allow}'
    )


def apply_loungemesh_embed_headers(response):
    response['Permissions-Policy'] = loungemesh_permissions_policy()
    origins = loungemesh_embed_origins()
    if not origins:
        return response
    existing = getattr(response, '_csp_update', None) or {}
    frame = [str(part) for part in existing.get('frame-src', []) if part]
    for origin in origins:
        if origin not in frame:
            frame.append(origin)
    existing['frame-src'] = frame
    response._csp_update = existing
    return response


def plugin_is_installed() -> bool:
    return apps.is_installed(LOUNGEMESH_PLUGIN_MODULE)


def plugin_enabled_for_event(event) -> bool:
    if not plugin_is_installed():
        return True
    plugin_list = getattr(event, 'plugin_list', None)
    if isinstance(plugin_list, list):
        return LOUNGEMESH_PLUGIN_MODULE in plugin_list
    plugins = getattr(event, 'plugins', '') or ''
    return LOUNGEMESH_PLUGIN_MODULE in plugins.split(',')


def loungemesh_is_available(event) -> bool:
    settings = get_loungemesh_settings()
    if not settings['enabled']:
        return False
    return plugin_enabled_for_event(event)


def jitsi_room_name(event, room) -> str:
    return f'lms-{event.slug}-{room.pk}'


def organizer_feature_allowlist() -> set[str]:
    return set(get_loungemesh_settings()['organizer_features'])


def sanitize_loungemesh_config(config: dict[str, Any] | None) -> dict[str, Any]:
    raw = config if isinstance(config, dict) else {}
    allowed = organizer_feature_allowlist()
    features: dict[str, bool] = {}
    incoming = raw.get('features')
    if not isinstance(incoming, dict):
        incoming = {key: bool(raw.get(key)) for key in ROOM_DEFAULT_FEATURE_KEYS if key in raw}
    for key in ROOM_DEFAULT_FEATURE_KEYS:
        features[key] = bool(incoming.get(key)) and key in allowed
    url_override = (raw.get('url') or '').strip()
    clean: dict[str, Any] = {'features': features}
    if url_override:
        clean['url'] = url_override
    return clean


def sanitize_loungemesh_modules(module_config: list | None) -> None:
    if not isinstance(module_config, list):
        return
    for module in module_config:
        if not isinstance(module, dict):
            continue
        if module.get('type') != LOUNGEMESH_MODULE_TYPE:
            continue
        module['config'] = sanitize_loungemesh_config(module.get('config'))


def room_has_loungemesh_module(room) -> bool:
    for module in room.module_config or []:
        if module.get('type') == LOUNGEMESH_MODULE_TYPE:
            return True
    return False


def room_feature_config(room) -> dict[str, bool]:
    for module in room.module_config or []:
        if module.get('type') != LOUNGEMESH_MODULE_TYPE:
            continue
        return sanitize_loungemesh_config(module.get('config')).get('features', {})
    return sanitize_loungemesh_config({}).get('features', {})


def room_base_url(room) -> str:
    settings = get_loungemesh_settings()
    for module in room.module_config or []:
        if module.get('type') != LOUNGEMESH_MODULE_TYPE:
            continue
        override = (module.get('config') or {}).get('url')
        if override:
            return str(override).rstrip('/')
    return settings['url']


def issue_jitsi_jwt(*, display_name: str, jitsi_room: str, moderator: bool, features: dict[str, bool]) -> str | None:
    settings = get_loungemesh_settings()
    app_id = settings['jitsi_app_id']
    app_secret = settings['jitsi_app_secret']
    if not app_id or not app_secret:
        return None
    now_dt = now()
    payload = {
        'aud': app_id,
        'iss': app_id,
        'sub': '*',
        'room': jitsi_room,
        'nbf': int(now_dt.timestamp()) - 10,
        'exp': int((now_dt + TOKEN_TTL).timestamp()),
        'context': {
            'user': {
                'name': display_name,
                'moderator': moderator,
            },
            'features': features,
        },
    }
    return jwt.encode(payload, app_secret, algorithm='HS256')


def issue_opaque_token(event, room, user, *, moderator: bool) -> LoungeMeshAccessToken:
    display_name = ''
    profile = getattr(user, 'profile', None)
    if isinstance(profile, dict):
        display_name = profile.get('display_name') or ''
    token = LoungeMeshAccessToken.objects.create(
        event=event,
        room=room,
        user=user,
        is_moderator=moderator,
        display_name=display_name,
        expires=now() + TOKEN_TTL,
    )
    return token


def verify_loungemesh_token(raw_token: str) -> LoungeMeshAccessToken | None:
    if not raw_token:
        return None
    with scopes_disabled():
        try:
            token = LoungeMeshAccessToken.objects.select_related('event', 'room', 'user').get(token=raw_token)
        except LoungeMeshAccessToken.DoesNotExist:
            return None
        if token.expires <= now():
            return None
        return token


def token_exchange_payload(access: LoungeMeshAccessToken) -> dict[str, Any]:
    with scope(event=access.event):
        if not loungemesh_is_available(access.event):
            return {}
        if not room_has_loungemesh_module(access.room):
            return {}
        features = room_feature_config(access.room)
        jitsi_room = jitsi_room_name(access.event, access.room)
        jwt_value = issue_jitsi_jwt(
            display_name=access.display_name,
            jitsi_room=jitsi_room,
            moderator=access.is_moderator,
            features=features,
        )
    return {
        'jwt': jwt_value,
        'display_name': access.display_name,
        'expires_at': access.expires.isoformat(),
        'jitsi_room': jitsi_room,
        'moderator': access.is_moderator,
        'features': features,
    }


def issue_join_url(event, room, user, *, moderator: bool) -> str | None:
    if not loungemesh_is_available(event):
        return None
    if not room_has_loungemesh_module(room):
        return None
    token = issue_opaque_token(event, room, user, moderator=moderator)
    jitsi_room = jitsi_room_name(event, room)
    query = urlencode(
        {
            'token': token.token,
            'event': event.slug,
            'room': str(room.pk),
        }
    )
    return f'{room_base_url(room)}/join/{jitsi_room}?{query}'
