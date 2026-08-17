from eventyay.core.permissions import Permission


# TODO(server-room-dev-gate): Remove this gate when server-backed room creation is released to normal roles.
SERVER_BACKED_ROOM_CREATE_PERMISSIONS = {
    "call.bigbluebutton": Permission.EVENT_ROOMS_CREATE_BBB,
    "call.janus": Permission.EVENT_ROOMS_CREATE_BBB,
    "call.jitsi": Permission.EVENT_ROOMS_CREATE_JITSI,
    "call.zoom": Permission.EVENT_ROOMS_CREATE_BBB,
    "networking.roulette": Permission.EVENT_ROOMS_CREATE_BBB,
}
SERVER_BACKED_ROOM_MODULE_TYPES = frozenset(SERVER_BACKED_ROOM_CREATE_PERMISSIONS)


def module_config_contains_server_backed_room(module_config):
    return any(
        isinstance(module, dict)
        and module.get("type") in SERVER_BACKED_ROOM_MODULE_TYPES
        for module in module_config or []
    )


def has_server_room_development_admin_trait(traits):
    # TODO(server-room-dev-gate): Remove when server-backed room creation is released to normal roles.
    return "admin" in (traits or [])


async def user_can_create_server_backed_room_during_development(user):
    # TODO(server-room-dev-gate): Remove when server-backed room creation is released to normal roles.
    return has_server_room_development_admin_trait(getattr(user, "traits", None))


def server_backed_room_create_permissions(module_config):
    permissions = {
        SERVER_BACKED_ROOM_CREATE_PERMISSIONS[module.get("type")]
        for module in module_config or []
        if isinstance(module, dict)
        and module.get("type") in SERVER_BACKED_ROOM_CREATE_PERMISSIONS
    }
    return sorted(permissions, key=lambda permission: permission.value)
