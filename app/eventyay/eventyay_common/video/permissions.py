from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from eventyay.base.models import Event


@dataclass(frozen=True)
class VideoPermissionDefinition:
    """Mapping from team permission field to video trait identifier."""

    field: str
    trait_name: str

    def trait_value(self, event_slug: str) -> str:
        normalized_trait = self.trait_name.replace('_', '-')
        return f'eventyay-video-event-{event_slug}-{normalized_trait}'


def video_attendee_trait(event_slug: str) -> str:
    """Event-scoped trait embedded in ticket/organizer JWTs for basic video access."""
    return f'eventyay-video-event-{event_slug}'


def resolve_attendee_trait_grant(event: Event, attendee_grant):
    """
    Require a JWT/ticket trait for attendee access unless the public video link is on.

    Anonymous client_id users get empty traits rewritten to ['attendee']; locking the
    default open grant blocks that path while preserving custom grants.
    """
    settings_obj = getattr(event, 'settings', None)
    if settings_obj is not None and settings_obj.get('venueless_show_public_link', False):
        return attendee_grant
    if attendee_grant in (None, ['attendee'], 'attendee'):
        slug = getattr(event, 'slug', None) or getattr(event, 'id', None)
        if slug:
            return [video_attendee_trait(slug)]
    return attendee_grant


VIDEO_PERMISSION_DEFINITIONS: dict[str, VideoPermissionDefinition] = {
    'can_video_create_stages': VideoPermissionDefinition('can_video_create_stages', 'video_stage_manager'),
    'can_video_create_channels': VideoPermissionDefinition('can_video_create_channels', 'video_channel_manager'),
    'can_video_manage_announcements': VideoPermissionDefinition('can_video_manage_announcements', 'video_announcement_manager'),
    'can_video_view_users': VideoPermissionDefinition('can_video_view_users', 'video_user_viewer'),
    'can_video_manage_users': VideoPermissionDefinition('can_video_manage_users', 'video_user_moderator'),
    'can_video_manage_rooms': VideoPermissionDefinition('can_video_manage_rooms', 'video_room_manager'),
    'can_video_manage_polls_questions': VideoPermissionDefinition('can_video_manage_polls_questions', 'video_poll_question_manager'),
    'can_video_manage_kiosks': VideoPermissionDefinition('can_video_manage_kiosks', 'video_kiosk_manager'),
    'can_video_manage_configuration': VideoPermissionDefinition('can_video_manage_configuration', 'video_config_manager'),
}

VIDEO_PERMISSION_BY_FIELD: dict[str, VideoPermissionDefinition] = VIDEO_PERMISSION_DEFINITIONS

VIDEO_PERMISSION_TRAIT_NAMES: list[str] = [
    definition.trait_name for definition in VIDEO_PERMISSION_DEFINITIONS.values()
]

VIDEO_TRAIT_ROLE_MAP: dict[str, str] = {
    # Map traits to roles; currently 1:1 but kept as a lookup for future divergence
    definition.trait_name: definition.trait_name
    for definition in VIDEO_PERMISSION_DEFINITIONS.values()
}


def iter_video_permission_definitions() -> Iterable[VideoPermissionDefinition]:
    return VIDEO_PERMISSION_DEFINITIONS.values()


def build_video_traits_for_event(event_slug: str) -> dict[str, str]:
    """
    Returns a mapping of trait name -> unique trait value for the given event slug.
    """
    return {
        definition.trait_name: definition.trait_value(event_slug)
        for definition in VIDEO_PERMISSION_DEFINITIONS.values()
    }


def collect_user_video_traits(event_slug: str, team_permission_set: Iterable[str]) -> list[str]:
    """
    Given an event slug and the permission set for the current user, return the list of
    video trait values that should be embedded into the JWT token.
    """
    traits = []
    for perm_name in team_permission_set:
        if definition := VIDEO_PERMISSION_BY_FIELD.get(perm_name):
            traits.append(definition.trait_value(event_slug))
    return traits
