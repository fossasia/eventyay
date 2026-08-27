from eventyay.base.services.room_creation_gate import (
    has_all_server_backed_room_create_permissions,
    newly_added_server_backed_room_modules,
    server_backed_room_create_permissions,
)
from eventyay.core.permissions import Permission


def test_newly_added_detects_first_server_backed_module():
    old = [{"type": "chat.native"}]
    new = [{"type": "chat.native"}, {"type": "call.bigbluebutton"}]
    added = newly_added_server_backed_room_modules(old, new)
    assert [m["type"] for m in added] == ["call.bigbluebutton"]


def test_newly_added_ignores_existing_server_backed_type():
    old = [{"type": "call.bigbluebutton"}]
    new = [{"type": "call.bigbluebutton", "config": {"updated": True}}]
    assert newly_added_server_backed_room_modules(old, new) == []


def test_newly_added_detects_second_module_of_same_type():
    old = [{"type": "call.bigbluebutton", "config": {"id": "a"}}]
    new = [
        {"type": "call.bigbluebutton", "config": {"id": "a"}},
        {"type": "call.bigbluebutton", "config": {"id": "b"}},
    ]
    added = newly_added_server_backed_room_modules(old, new)
    assert len(added) == 1
    assert added[0]["config"]["id"] == "b"


def test_newly_added_detects_additional_distinct_server_backed_type():
    old = [{"type": "call.bigbluebutton"}]
    new = [{"type": "call.bigbluebutton"}, {"type": "call.jitsi"}]
    added = newly_added_server_backed_room_modules(old, new)
    assert [m["type"] for m in added] == ["call.jitsi"]


def test_server_backed_create_permissions_are_distinct():
    perms = server_backed_room_create_permissions(
        [{"type": "call.bigbluebutton"}, {"type": "call.jitsi"}]
    )
    assert set(perms) == {
        Permission.EVENT_ROOMS_CREATE_BBB,
        Permission.EVENT_ROOMS_CREATE_JITSI,
    }


def test_has_all_server_backed_create_permissions_requires_each(monkeypatch):
    class FakeEvent:
        def __init__(self):
            self.calls = []

        def has_permission_implicit(self, *, traits, permissions):
            self.calls.append(permissions)
            # Grant BBB only; deny Jitsi.
            return permissions == [Permission.EVENT_ROOMS_CREATE_BBB]

    event = FakeEvent()
    assert not has_all_server_backed_room_create_permissions(
        event,
        traits=["admin"],
        module_config=[{"type": "call.bigbluebutton"}, {"type": "call.jitsi"}],
    )
    assert event.calls == [
        [Permission.EVENT_ROOMS_CREATE_BBB],
        [Permission.EVENT_ROOMS_CREATE_JITSI],
    ]

    event = FakeEvent()
    event.has_permission_implicit = lambda **kwargs: True
    assert has_all_server_backed_room_create_permissions(
        event,
        traits=["admin"],
        module_config=[{"type": "call.bigbluebutton"}, {"type": "call.jitsi"}],
    )
