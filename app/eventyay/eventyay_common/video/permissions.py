from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class VideoPermissionDefinition:
    """Mapping from team permission field to video trait identifier."""

    field: str
    trait_name: str

    def trait_value(self, event_slug: str) -> str:
        normalized_trait = self.trait_name.replace('_', '-')
        return f'eventyay-video-event-{event_slug}-{normalized_trait}'


VIDEO_PERMISSION_DEFINITIONS: List[VideoPermissionDefinition] = [
    VideoPermissionDefinition('can_video_create_stages', 'video_stage_manager'),
    VideoPermissionDefinition('can_video_create_channels', 'video_channel_manager'),
    VideoPermissionDefinition('can_video_direct_message', 'video_direct_messaging'),
    VideoPermissionDefinition('can_video_manage_announcements', 'video_announcement_manager'),
    VideoPermissionDefinition('can_video_view_users', 'video_user_viewer'),
    VideoPermissionDefinition('can_video_manage_users', 'video_user_moderator'),
    VideoPermissionDefinition('can_video_manage_rooms', 'video_room_manager'),
    VideoPermissionDefinition('can_video_manage_kiosks', 'video_kiosk_manager'),
    VideoPermissionDefinition('can_video_manage_configuration', 'video_config_manager'),
]

VIDEO_PERMISSION_BY_FIELD: Dict[str, VideoPermissionDefinition] = {
    definition.field: definition for definition in VIDEO_PERMISSION_DEFINITIONS
}

VIDEO_PERMISSION_TRAIT_NAMES: List[str] = [
    definition.trait_name for definition in VIDEO_PERMISSION_DEFINITIONS
]

VIDEO_TRAIT_ROLE_MAP: Dict[str, str] = {
    definition.trait_name: definition.trait_name
    for definition in VIDEO_PERMISSION_DEFINITIONS
}


def iter_video_permission_definitions() -> Iterable[VideoPermissionDefinition]:
    return VIDEO_PERMISSION_DEFINITIONS


def build_video_traits_for_event(event_slug: str) -> Dict[str, str]:
    """
    Returns a mapping of trait name -> unique trait value for the given event slug.
    """
    return {
        definition.trait_name: definition.trait_value(event_slug)
        for definition in VIDEO_PERMISSION_DEFINITIONS
    }


def collect_user_video_traits(event_slug: str, team_permission_set: Iterable[str]) -> List[str]:
    """
    Given an event slug and the permission set for the current user, return the list of
    video trait values that should be embedded into the JWT token.
    """
    traits = []
    for perm_name in team_permission_set:
        if definition := VIDEO_PERMISSION_BY_FIELD.get(perm_name):
            traits.append(definition.trait_value(event_slug))
    return traits

