from enum import Enum


class Permission(Enum):
    EVENT_VIEW = "event.view"
    EVENT_UPDATE = "event.update"
    EVENT_ANNOUNCE = "event:announce"
    EVENT_SECRETS = "event:secrets"
    EVENT_API = "event:api"
    EVENT_GRAPHS = "event:graphs"
    EVENT_ROOMS_CREATE_STAGE = "event:rooms.create.stage"
    EVENT_ROOMS_CREATE_CHAT = "event:rooms.create.chat"
    EVENT_ROOMS_CREATE_BBB = "event:rooms.create.bbb"
    EVENT_ROOMS_CREATE_EXHIBITION = "event:rooms.create.exhibition"
    EVENT_ROOMS_CREATE_POSTER = "event:rooms.create.poster"
    EVENT_USERS_LIST = "event:users.list"
    EVENT_USERS_MANAGE = "event:users.manage"
    EVENT_KIOSKS_MANAGE = "event:kiosks.manage"
    EVENT_CHAT_DIRECT = "event:chat.direct"
    EVENT_EXHIBITION_CONTACT = "event:exhibition.contact"
    EVENT_CONNECTIONS_UNLIMITED = "event:connections.unlimited"
    ROOM_ANNOUNCE = "room:announce"
    ROOM_VIEW = "room:view"
    ROOM_UPDATE = "room:update"
    ROOM_DELETE = "room:delete"
    ROOM_CHAT_READ = "room:chat.read"
    ROOM_CHAT_JOIN = "room:chat.join"
    ROOM_CHAT_SEND = "room:chat.send"
    ROOM_VIEWERS = "room:viewers"
    ROOM_INVITE = "room:invite"
    ROOM_INVITE_ANONYMOUS = "room:invite.anonymous"
    ROOM_CHAT_MODERATE = "room:chat.moderate"
    ROOM_JANUSCALL_JOIN = "room:januscall.join"
    ROOM_JANUSCALL_MODERATE = "room:januscall.moderate"
    ROOM_BBB_JOIN = "room:bbb.join"
    ROOM_BBB_MODERATE = "room:bbb.moderate"
    ROOM_BBB_RECORDINGS = "room:bbb.recordings"
    ROOM_ZOOM_JOIN = "room:zoom.join"
    ROOM_QUESTION_READ = "room:question.read"
    ROOM_QUESTION_ASK = "room:question.ask"
    ROOM_QUESTION_VOTE = "room:question.vote"
    ROOM_QUESTION_MODERATE = "room:question.moderate"
    ROOM_ROULETTE_JOIN = "room:roulette.join"
    ROOM_POLL_READ = "room:poll.read"
    ROOM_POLL_EARLY_RESULTS = "room:poll.early_results"
    ROOM_POLL_VOTE = "room:poll.vote"
    ROOM_POLL_MANAGE = "room:poll.manage"


MAX_PERMISSIONS_IF_SILENCED = {
    Permission.EVENT_VIEW,
    Permission.ROOM_VIEW,
    Permission.ROOM_CHAT_READ,
    Permission.ROOM_CHAT_JOIN,
}


SYSTEM_ROLES = {
    "__kiosk": [
        Permission.EVENT_VIEW.value,
        Permission.ROOM_VIEW.value,
        Permission.ROOM_CHAT_READ.value,
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_EARLY_RESULTS.value,
        Permission.ROOM_VIEWERS.value,
        Permission.ROOM_INVITE_ANONYMOUS.value,
    ],
    "__anonymous_event": [
        Permission.EVENT_VIEW.value,
    ],
    "__anonymous_room": [
        Permission.ROOM_QUESTION_READ.value,
        Permission.ROOM_QUESTION_ASK.value,
        Permission.ROOM_QUESTION_VOTE.value,
        Permission.ROOM_POLL_READ.value,
        Permission.ROOM_POLL_VOTE.value,
        Permission.ROOM_VIEW.value,
    ],
    "video_stage_manager": [
        Permission.EVENT_ROOMS_CREATE_STAGE.value,
    ],
    "video_channel_manager": [
        Permission.EVENT_ROOMS_CREATE_CHAT.value,
        Permission.EVENT_ROOMS_CREATE_BBB.value,
    ],
    "video_direct_messaging": [
        Permission.EVENT_CHAT_DIRECT.value,
    ],
    "video_announcement_manager": [
        Permission.EVENT_ANNOUNCE.value,
    ],
    "video_user_viewer": [
        Permission.EVENT_USERS_LIST.value,
    ],
    "video_user_moderator": [
        Permission.EVENT_USERS_MANAGE.value,
    ],
    "video_room_manager": [
        Permission.ROOM_UPDATE.value,
        Permission.ROOM_DELETE.value,
    ],
    "video_kiosk_manager": [
        Permission.EVENT_KIOSKS_MANAGE.value,
    ],
    "video_config_manager": [
        Permission.EVENT_UPDATE.value,
    ],
}

# Roles that are considered organizer/admin roles for permission management
ORGANIZER_ROLES = frozenset({
    'admin',
    'apiuser',
    'scheduleuser',
    'video_stage_manager',
    'video_channel_manager',
    'video_announcement_manager',
    'video_user_viewer',
    'video_user_moderator',
    'video_room_manager',
    'video_kiosk_manager',
    'video_config_manager',
    'video_direct_messaging',
})


def normalize_permission_value(permission):
    """Normalize permission to string value for comparison.
    
    Args:
        permission: Permission enum or string value
        
    Returns:
        str: Permission value as string
    """
    return permission if isinstance(permission, str) else permission.value


def traits_match_required(traits: list[str], required_traits: list) -> bool:
    """Check if user traits match required traits for a role.
    
    Args:
        traits: List of user traits
        required_traits: List of required traits (can contain nested lists for OR logic)
        
    Returns:
        bool: True if all required traits are matched
    """
    if not isinstance(required_traits, list):
        return False
    
    return all(
        any(x in traits for x in (r if isinstance(r, list) else [r]))
        for r in required_traits
    )
