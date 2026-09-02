from __future__ import annotations

from django.db.models import Q

from eventyay.base.settings import GlobalSettingsObject

MODULE_TYPE_SETTING_KEYS = {
    'call.bigbluebutton': 'video_bbb_enabled',
    'call.jitsi': 'video_jitsi_enabled',
    'call.janus': 'video_janus_enabled',
    'livestream.native': 'video_streaming_enabled',
    'livestream.youtube': 'video_streaming_enabled',
    'livestream.iframe': 'video_streaming_enabled',
    'chat.native': 'video_chat_channels_enabled',
    'question': 'video_qna_enabled',
    'poll': 'video_polls_enabled',
}

FEATURE_FLAG_SETTING_KEYS = {
    'chat': 'video_chat_channels_enabled',
    'question': 'video_qna_enabled',
    'polls': 'video_polls_enabled',
    'stream': 'video_streaming_enabled',
    'bbb': 'video_bbb_enabled',
    'jitsi': 'video_jitsi_enabled',
    'janus': 'video_janus_enabled',
}

SETTING_LABELS = {
    'video_jitsi_enabled': 'Jitsi',
    'video_bbb_enabled': 'BigBlueButton',
    'video_janus_enabled': 'Janus',
    'video_streaming_enabled': 'Streaming',
    'video_chat_channels_enabled': 'Chat channels',
    'video_qna_enabled': 'Q&A',
    'video_polls_enabled': 'Polls',
}

SETTING_MODULE_TYPES = {
    'video_jitsi_enabled': ['call.jitsi'],
    'video_bbb_enabled': ['call.bigbluebutton'],
    'video_janus_enabled': ['call.janus'],
    'video_streaming_enabled': [
        'livestream.native',
        'livestream.youtube',
        'livestream.iframe',
    ],
    'video_chat_channels_enabled': ['chat.native'],
    'video_qna_enabled': ['question'],
    'video_polls_enabled': ['poll'],
}


def is_video_component_setting_enabled(setting_key: str, gs: GlobalSettingsObject | None = None) -> bool:
    if gs is None:
        gs = GlobalSettingsObject()
    return gs.settings.get(setting_key, as_type=bool, default=True)


def is_module_type_enabled(module_type: str, gs: GlobalSettingsObject | None = None) -> bool:
    setting_key = MODULE_TYPE_SETTING_KEYS.get(module_type)
    if setting_key is None:
        return True
    return is_video_component_setting_enabled(setting_key, gs=gs)


def get_global_video_component_flags(gs: GlobalSettingsObject | None = None) -> dict[str, bool]:
    if gs is None:
        gs = GlobalSettingsObject()
    return {
        flag: is_video_component_setting_enabled(setting_key, gs=gs)
        for flag, setting_key in FEATURE_FLAG_SETTING_KEYS.items()
    }


def apply_global_video_component_flags(flags: dict) -> dict[str, bool]:
    merged = dict(flags)
    for flag, enabled in get_global_video_component_flags().items():
        merged[flag] = bool(enabled)

    if not merged.get('chat'):
        merged['question'] = False
        merged['polls'] = False

    return merged


def get_disabled_module_error(module_type: str) -> str:
    label = SETTING_LABELS.get(
        MODULE_TYPE_SETTING_KEYS.get(module_type, ''),
        module_type,
    )
    return f'{label} is currently disabled by the platform administrator.'


def get_video_component_usage() -> dict[str, dict[str, int]]:
    from eventyay.base.models import Room

    usage = {}
    for setting_key, module_types in SETTING_MODULE_TYPES.items():
        query = Q()
        for module_type in module_types:
            query |= Q(module_config__contains=[{'type': module_type}])
        rooms = Room.objects.filter(query).select_related('event')
        event_ids = set()
        room_count = 0
        for room in rooms:
            module_config = room.module_config or []
            if not isinstance(module_config, list):
                continue
            room_types = {
                module.get('type')
                for module in module_config
                if isinstance(module, dict) and module.get('type')
            }
            if room_types.intersection(module_types):
                room_count += 1
                event_ids.add(room.event_id)
        usage[setting_key] = {
            'rooms': room_count,
            'events': len(event_ids),
        }
    return usage
