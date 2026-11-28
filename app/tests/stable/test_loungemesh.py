import asyncio
import json
import time
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
import requests
from django.test import Client, override_settings
from django.utils import timezone
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, LoungeMeshServer, Organizer, Room, User
from eventyay.base.services.loungemesh import (
    apply_loungemesh_embed_headers,
    get_available_loungemesh_servers,
    get_loungemesh_server,
    is_event_accessible_for_role,
    issue_join_url,
    issue_signed_grant,
    loungemesh_embed_origins,
    loungemesh_is_available,
    loungemesh_permissions_policy,
    resolve_loungemesh_role,
    serialize_loungemesh_server,
    validate_loungemesh_server_url,
)
from eventyay.base.services.loungemesh import (
    test_loungemesh_server_connection as svc_test_loungemesh_server_connection,
)
from eventyay.control.forms.server_management import LoungeMeshServerForm
from eventyay.core.permissions import Permission
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.loungemesh import LoungeMeshModule


@pytest.fixture
def test_setup(allow_all_entitlements):
    with patch("eventyay.base.models.cache.VersionedModel._set_cache_version_sync"):
        with scopes_disabled():
            organizer = Organizer.objects.create(name="LoungeMesh Org", slug="lm-org")
            event = Event.objects.create(
                organizer=organizer,
                name="LoungeMesh Event",
                slug="lm-event",
                date_from=timezone.now() - timedelta(hours=1),
                date_to=timezone.now() + timedelta(days=2),
                live=True,
            )
            user = User.objects.create(
                email="attendee@example.com",
                fullname="Alice Attendee",
            )
            admin_user = User.objects.create(
                email="admin@example.com",
                fullname="Admin User",
                is_administrator=True,
                is_staff=True,
            )
            moderator_user = User.objects.create(
                email="mod@example.com",
                fullname="Bob Moderator",
            )
            server = LoungeMeshServer.objects.create(
                url="http://localhost:8780",
                api_secret="test_lm_secret_long_enough_for_jwt_signing_32b",
                active=True,
                cost=0,
            )
            with scope(event=event):
                room = Room.objects.create(
                    event=event,
                    name="Spatial Lounge",
                    module_config=[
                        {
                            "type": "call.loungemesh",
                            "config": {
                                "prefer_server": "http://localhost:8780",
                                "enable_notes": True,
                                "enable_whiteboard": True,
                                "enable_spatial_chat": True,
                                "features": {
                                    "notes": True,
                                    "whiteboard": True,
                                    "spatial_chat": True,
                                },
                            },
                        }
                    ],
                )

        yield {
            "organizer": organizer,
            "event": event,
            "user": user,
            "admin_user": admin_user,
            "moderator_user": moderator_user,
            "server": server,
            "room": room,
        }


@pytest.mark.django_db
def test_loungemesh_server_model_and_form(test_setup):
    server = test_setup["server"]
    assert str(server) == "http://localhost:8780"
    assert server.active is True
    assert server.cost == 0

    # Test Form validation and normalization
    form_data = {
        "url": "http://localhost:8780/",
        "api_secret": "my_secret_32_chars_long_for_tests",
        "active": True,
    }
    form = LoungeMeshServerForm(data=form_data)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.url == "http://localhost:8780"  # trailing slash stripped


@pytest.mark.django_db
def test_validate_loungemesh_server_url():
    # Empty
    valid, _ = validate_loungemesh_server_url("")
    assert not valid

    # Embedded credentials
    valid, msg = validate_loungemesh_server_url("https://user:pass@example.com")
    assert not valid
    assert "credentials" in str(msg)

    # Invalid scheme
    valid, msg = validate_loungemesh_server_url("ftp://example.com")
    assert not valid
    assert "scheme" in str(msg)

    # Localhost
    valid, _ = validate_loungemesh_server_url("http://localhost:8780")
    assert valid

    valid, _ = validate_loungemesh_server_url("http://127.0.0.1:8780")
    assert valid

    # Malformed URL authority (does not crash with unhandled ValueError)
    valid, msg = validate_loungemesh_server_url("https://[")
    assert not valid
    assert "Invalid URL" in str(msg)

    # SSRF protection does NOT get disabled by executable path containing 'latest'
    with (
        override_settings(DEBUG=False, IS_TESTING=False),
        patch.dict("os.environ", {"EVY_RUNNING_ENVIRONMENT": "production"}),
        patch.dict("sys.modules", {"pytest": None}),
        patch("sys.argv", ["/opt/eventyay/latest/bin/gunicorn"]),
    ):
        valid, msg = validate_loungemesh_server_url("http://127.0.0.1:8780")
        assert not valid
        assert "production" in str(msg).lower()


@pytest.mark.django_db
def test_connection_testing():
    # 1. Successful connection
    class MockSuccessResponse:
        status_code = 200

        def json(self):
            return {"ok": True, "service": "loungemesh"}

    with patch("requests.Session.get", return_value=MockSuccessResponse()):
        ok, msg = svc_test_loungemesh_server_connection("http://localhost:8780", "secret123")
        assert ok is True
        assert msg == "ok"

    # 2. 401 Unauthorized
    class Mock401Response:
        status_code = 401

    with patch("requests.Session.get", return_value=Mock401Response()):
        ok, msg = svc_test_loungemesh_server_connection("http://localhost:8780", "wrongsecret")
        assert ok is False
        assert "secret" in str(msg).lower()

    # 3. 404 Endpoint Not Found
    class Mock404Response:
        status_code = 404

    with patch("requests.Session.get", return_value=Mock404Response()):
        ok, msg = svc_test_loungemesh_server_connection("http://localhost:8780", "secret123")
        assert ok is False
        assert "404" in str(msg)

    # 4. Connection timeout
    with patch("requests.Session.get", side_effect=requests.exceptions.Timeout()):
        ok, msg = svc_test_loungemesh_server_connection("http://localhost:8780", "secret123")
        assert ok is False
        assert "timed out" in str(msg).lower()


@pytest.mark.django_db
def test_get_loungemesh_server_selection(test_setup):
    event = test_setup["event"]
    server = test_setup["server"]

    # When active server is present
    selected = get_loungemesh_server(event=event)
    assert selected == server
    assert loungemesh_is_available(event=event) is True

    # Preferred server selection by URL
    preferred = get_loungemesh_server(event=event, prefer_server="http://localhost:8780")
    assert preferred == server

    # Preferred server selection by UUID
    preferred_uuid = get_loungemesh_server(event=event, prefer_server=str(server.pk))
    assert preferred_uuid == server

    # If all servers are inactive
    server.active = False
    server.save()
    assert get_loungemesh_server(event=event) is None
    assert loungemesh_is_available(event=event) is False

    # Reset server active state for subsequent tests
    server.active = True
    server.save()


@pytest.mark.django_db
def test_get_available_and_serialize_servers(test_setup):
    event = test_setup["event"]
    organizer = test_setup["organizer"]
    server = test_setup["server"]

    with scopes_disabled():
        # Create organizer-scoped server
        org_server = LoungeMeshServer.objects.create(
            url="https://org.loungemesh.example.com",
            api_secret="org_secret_32_chars_long_for_test",
            active=True,
        )
        org_server.organizers.add(organizer)

        # Create custom event-exclusive server
        event_server = LoungeMeshServer.objects.create(
            url="https://custom.loungemesh.example.com",
            api_secret="custom_secret_32_chars_long_test",
            active=True,
            event_exclusive=event,
            is_user_managed=True,
        )
        event_server.events.add(event)

        # Create admin-assigned event-exclusive server (not user-managed)
        admin_event_server = LoungeMeshServer.objects.create(
            url="https://admin-assigned.loungemesh.example.com",
            api_secret="admin_secret_32_chars_long_test",
            active=True,
            event_exclusive=event,
            is_user_managed=False,
        )
        admin_event_server.events.add(event)

    available = get_available_loungemesh_servers(event)
    # Event-exclusive comes first, then organizer, then global
    assert available[0] in (event_server, admin_event_server)
    assert available[1] in (event_server, admin_event_server)
    assert available[2] == org_server
    assert available[3] == server

    ser = serialize_loungemesh_server(event_server, event)
    assert ser["url"] == "https://custom.loungemesh.example.com"
    assert ser["scope"] == "event"
    assert ser["is_custom"] is True
    assert "api_secret" not in ser

    admin_ser = serialize_loungemesh_server(admin_event_server, event)
    assert admin_ser["url"] == "https://admin-assigned.loungemesh.example.com"
    assert admin_ser["scope"] == "event"
    assert admin_ser["is_custom"] is False


@pytest.mark.django_db
def test_resolve_loungemesh_role(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]

    # Unprivileged user -> attendee
    assert resolve_loungemesh_role(event, user) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"

    # Stored traits without verified permissions/session must NOT elevate to host or moderator
    user.traits = ["admin"]
    assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"
    user.traits = []

    # Attendee tokens (not ending in :orga) must always resolve to attendee
    user.token_id = "B4CE158"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"
    user.token_id = None

    # can_video_manage_content in organizer area -> host, public view -> attendee
    def host_content_check(org, ev, perm):
        return perm == "can_video_manage_content"

    with patch.object(user, "has_event_permission", side_effect=host_content_check):
        assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
        assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "host"

    # can_change_config -> attendee (config is for themes/defaults, not host)
    def host_config_check(org, ev, perm):
        return perm == "can_change_config"

    with patch.object(user, "has_event_permission", side_effect=host_config_check):
        assert resolve_loungemesh_role(event, user) == "attendee"
        assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"

    # can_video_moderate in organizer area -> moderator, public view -> attendee
    def mod_check(org, ev, perm):
        return perm == "can_video_moderate"

    with patch.object(user, "has_event_permission", side_effect=mod_check):
        assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
        assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "moderator"

    # Stored video traits without platform permission must NOT elevate role
    content_trait = f"eventyay-video-event-{event.slug}-video-content-manager"
    user.traits = [content_trait]
    assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"
    user.traits = []

    config_trait = f"eventyay-video-event-{event.slug}-video-config-manager"
    user.traits = [config_trait]
    assert resolve_loungemesh_role(event, user) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"
    user.traits = []

    moderator_trait = f"eventyay-video-event-{event.slug}-video-moderator"
    user.traits = [moderator_trait]
    assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
    assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"
    user.traits = []

    # Non-video permissions (including can_change_event_settings) -> attendee
    def other_check(org, ev, perm):
        return perm in ("can_change_items", "can_change_submissions", "can_change_event_settings")

    with patch.object(user, "has_event_permission", side_effect=other_check):
        assert resolve_loungemesh_role(event, user) == "attendee"
        assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "attendee"

    # User with only moderator permission must resolve to moderator, even if stale content trait is present
    user.traits = [content_trait]
    with patch.object(user, "has_event_permission", side_effect=mod_check):
        assert resolve_loungemesh_role(event, user, is_organizer_area=False) == "attendee"
        assert resolve_loungemesh_role(event, user, is_organizer_area=True) == "moderator"
    user.traits = []

    # Staff user without active admin mode and with moderator permissions syncs without 'admin' trait
    from eventyay.base.services.user import create_user, encode_email
    from eventyay.eventyay_common.video.traits_sync import sync_video_traits_for_platform_users
    staff_user = test_setup["admin_user"]
    staff_user.is_staff = True
    staff_token = f"{encode_email(staff_user.email).upper()}:ORGA"
    with scope(event=event):
        vuser = create_user(
            event_id=event.id,
            token_id=staff_token,
            traits=["admin", f"eventyay-video-event-{event.slug}-organizer"],
            profile={"contact_email": staff_user.email},
        )
    with patch.object(staff_user, "has_active_staff_session", return_value=False), \
         patch.object(staff_user, "get_event_permission_set", return_value={"can_video_moderate"}):
        sync_video_traits_for_platform_users(event.organizer, [staff_user], force_reload=False)
        vuser.refresh_from_db()
        assert "admin" not in vuser.traits
        assert f"eventyay-video-event-{event.slug}-video-moderator" in vuser.traits

    # Without verified platform_user binding, event-scoped vuser resolves to attendee even with organizer token/email
    assert resolve_loungemesh_role(event, vuser, is_organizer_area=True) == "attendee"
    with patch.object(staff_user, "has_event_permission", side_effect=mod_check):
        assert resolve_loungemesh_role(event, vuser, is_organizer_area=True, platform_user=staff_user) == "moderator"

    # Superuser with team moderator permission resolves to moderator unless current session has active StaffSession
    superuser = User.objects.create(
        email="supermod@example.com",
        is_staff=True,
        is_superuser=True,
    )
    super_token = f"{encode_email(superuser.email).upper()}:ORGA"
    with scope(event=event):
        super_vuser = create_user(
            event_id=event.id,
            token_id=super_token,
            traits=["attendee", f"eventyay-video-event-{event.slug}-organizer"],
            profile={"contact_email": superuser.email},
        )
    with patch.object(User, "has_active_staff_session", return_value=False), \
         patch.object(User, "has_event_permission", side_effect=lambda org, ev, perm: perm == "can_video_moderate"):
        assert resolve_loungemesh_role(event, superuser, is_organizer_area=True, session_key="sess-1") == "moderator"
        assert (
            resolve_loungemesh_role(
                event, super_vuser, is_organizer_area=True, platform_user=superuser, session_key="sess-1"
            )
            == "moderator"
        )

    # Even if has_active_staff_session is True, missing session_key must NOT elevate to host
    with patch.object(User, "has_active_staff_session", return_value=True), \
         patch.object(User, "has_event_permission", side_effect=lambda org, ev, perm: perm == "can_video_moderate"):
        assert resolve_loungemesh_role(event, superuser, is_organizer_area=True) == "moderator"
        assert resolve_loungemesh_role(event, superuser, is_organizer_area=True, session_key="sess-1") == "host"
        assert (
            resolve_loungemesh_role(
                event, super_vuser, is_organizer_area=True, platform_user=superuser, session_key="sess-1"
            )
            == "host"
        )

    # Superuser without team permissions still resolves to host via is_platform_event_admin
    with patch.object(User, "has_active_staff_session", return_value=False), \
         patch.object(User, "has_event_permission", return_value=False):
        assert resolve_loungemesh_role(event, superuser, is_organizer_area=True) == "host"
        assert (
            resolve_loungemesh_role(event, super_vuser, is_organizer_area=True, platform_user=superuser) == "host"
        )


@pytest.mark.django_db
def test_issue_signed_grant_and_join_url(test_setup):
    server = test_setup["server"]
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    # 1. issue_signed_grant
    grant = issue_signed_grant(event, room, user, role="host", server=server)
    assert isinstance(grant, str)

    payload = jwt.decode(grant, server.api_secret, algorithms=["HS256"], audience="loungemesh")
    assert payload["iss"] == "eventyay"
    assert payload["aud"] == "loungemesh"
    assert payload["sub"] == str(user.pk)
    assert payload["event"] == event.slug
    assert payload["room"] == str(room.pk)
    assert payload["jitsi_room"] == f"lms-{event.slug}-{room.pk}"
    assert payload["role"] == "host"
    assert payload["allowed"] is True

    # 2. issue_join_url
    join_url = issue_join_url(event=event, room=room, user=user, server=server)
    assert join_url is not None
    assert join_url.startswith("http://localhost:8780/join/")
    assert "?grant=" in join_url
    assert f"/join/lms-{event.slug}-{room.pk}" in join_url


@pytest.mark.django_db
def test_admin_server_test_view(test_setup):
    client = Client()
    admin_user = test_setup["admin_user"]
    client.force_login(admin_user)

    class MockSuccessResponse:
        status_code = 200

        def json(self):
            return {"ok": True, "service": "loungemesh"}

    with (
        patch.object(admin_user.__class__, "has_active_staff_session", return_value=True),
        patch("requests.Session.get", return_value=MockSuccessResponse()),
    ):
        test_payload = {
            "url": "http://localhost:8780",
            "api_secret": "test_lm_secret_long_enough_for_jwt_signing_32b",
        }
        resp = client.post(
            "/admin/video/loungemesh/test/",
            data=json.dumps(test_payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class DummyConsumer:
    def __init__(self, user, world, permissions=None, room_cache=None, is_organizer=False):
        self.user = user
        self.world = world
        self.event = world
        self.permissions = set(permissions or [])
        self.room_cache = room_cache or {}
        self.sent_data = None
        self.is_organizer = is_organizer

    async def has_permission_async(self, perm):
        perms_list = perm if isinstance(perm, (list, set, tuple)) else [perm]
        return any(
            (p.value if hasattr(p, "value") else str(p)) in self.permissions or p in self.permissions
            for p in perms_list
        )

    def has_permission(self, perm):
        perms_list = perm if isinstance(perm, (list, set, tuple)) else [perm]
        return any(
            (p.value if hasattr(p, "value") else str(p)) in self.permissions or p in self.permissions
            for p in perms_list
        )

    async def send_success(self, data):
        self.sent_data = data
        return data


@pytest.mark.django_db
def test_loungemesh_websocket_module(test_setup, monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]
    server = test_setup["server"]

    # Ensure server is active
    server.active = True
    server.save()

    room_cache = {str(room.id): room}

    consumer = DummyConsumer(
        user=user,
        world=event,
        permissions=[
            Permission.ROOM_LOUNGEMESH_JOIN.value,
            Permission.ROOM_UPDATE.value,
            Permission.EVENT_UPDATE.value,
        ],
        room_cache=room_cache,
    )
    consumer.event.has_permission_async = AsyncMock(return_value=True)

    module = LoungeMeshModule(consumer)

    def sync_to_async_mock(fn):
        async def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    fake_join_url = f"http://localhost:8780/join/lms-{event.slug}-{room.id}?grant=testgranttoken123"

    from django.db import connections
    main_conn = connections["default"]

    with (
        patch.object(connections.__class__, "__getitem__", return_value=main_conn),
        patch("channels.db.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.decorators.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.modules.loungemesh.database_sync_to_async", sync_to_async_mock),
        patch.object(room, "refresh_from_db_if_outdated", new_callable=AsyncMock),
        patch.object(module, "_get_join_url", new_callable=AsyncMock, return_value=fake_join_url),
    ):
        async def run_flow():
            # 1. servers command
            await module.servers({})
            servers_res = consumer.sent_data
            assert "servers" in servers_res
            assert len(servers_res["servers"]) >= 1
            assert servers_res["servers"][0]["url"] == server.url

            # 2. room_url command (public view: always attendee)
            await module.room_url({"room": str(room.id)})

            res = consumer.sent_data
            assert res is not None
            assert "url" in res
            assert "grant=" in res["url"]
            # Unprivileged user -> attendee
            assert res["role"] == "attendee"
            assert res["moderator"] is False

            # With active StaffSession on current session key in public view, attendee role is still enforced
            from eventyay.base.models.auth import StaffSession

            admin_user = test_setup["admin_user"]
            consumer.platform_user = admin_user
            consumer.session_key = "ws-module-session"
            StaffSession.objects.create(user=admin_user, session_key="ws-module-session")
            await module.room_url({"room": str(room.id)})
            assert consumer.sent_data["role"] == "attendee"
            assert consumer.sent_data["moderator"] is False

            # In organizer area with matching session-bound StaffSession, host role is resolved
            consumer.is_organizer = True
            await module.room_url({"room": str(room.id)})
            assert consumer.sent_data["role"] == "host"
            assert consumer.sent_data["moderator"] is True

            # Reset back to public view for remaining tests
            consumer.is_organizer = False
            consumer.platform_user = None
            consumer.session_key = None

            # 3. test_server command
            class MockSuccessResponse:
                status_code = 200

                def json(self):
                    return {"ok": True, "service": "loungemesh"}

            with patch("requests.Session.get", return_value=MockSuccessResponse()):
                await module.test_server({"url": "http://localhost:8780", "api_secret": "secret123"})
                test_res = consumer.sent_data
                assert test_res["ok"] is True

            # 4. add_server command (tested before saving)
            with patch("requests.Session.get", return_value=MockSuccessResponse()):
                await module.add_server({"url": "http://localhost:8781", "api_secret": "newsecret"})
                added = consumer.sent_data
                assert added["url"] == "http://localhost:8781"
                assert added["scope"] == "event"
                assert added["is_custom"] is True

            # 5. delete_server command
            custom_server_id = consumer.sent_data["id"]
            await module.delete_server({"server_id": custom_server_id})
            assert consumer.sent_data["ok"] is True

            # Attempting to delete a global server should raise ConsumerException
            with pytest.raises(ConsumerException):
                await module.delete_server({"server_id": str(server.pk)})

        asyncio.run(run_flow())


@pytest.mark.django_db
def test_embed_headers_and_permissions_policy(test_setup):
    policy = loungemesh_permissions_policy(["http://localhost:8780"])
    assert "camera=(self" in policy
    assert '"http://localhost:8780"' in policy
    assert "microphone=(self" in policy
    assert "display-capture=(self" in policy

    class MockResponse(dict):
        pass

    response = MockResponse()
    apply_loungemesh_embed_headers(response, ["http://localhost:8780"])
    assert "Permissions-Policy" in response


@pytest.mark.django_db
def test_loungemesh_grant_features_and_destination_binding(test_setup, client):
    import json
    from unittest.mock import patch

    import jwt

    from eventyay.base.services.loungemesh import _resolve_platform_principal, issue_signed_grant

    event = test_setup["event"]
    server = test_setup["server"]
    user = test_setup["user"]
    admin_user = test_setup["admin_user"]

    # 1. Grant includes features
    features_dict = {"notes": True, "whiteboard": False, "spatial_chat": True}
    token = issue_signed_grant(event, "hallway", user, "host", server=server, features=features_dict)
    claims = jwt.decode(token, server.api_secret, algorithms=["HS256"], audience="loungemesh")
    assert "features" in claims
    assert claims["features"] == features_dict

    # 2. _resolve_platform_principal requires verified platform binding (never email fallback)
    class MockEventUser:
        event_id = event.pk
        email = user.email
        profile = {"contact_email": user.email}

    assert _resolve_platform_principal(MockEventUser()) is None
    assert _resolve_platform_principal(MockEventUser(), platform_user=user) == user

    class BoundEventUser:
        event_id = event.pk
        platform_user = user

    assert _resolve_platform_principal(BoundEventUser()) == user

    # 3. Destination binding in LoungeMeshServerTestView
    client.force_login(admin_user)
    with patch.object(admin_user.__class__, "has_active_staff_session", return_value=True):
        # Mismatched URL when reusing stored secret
        req_data = {
            "server_id": str(server.pk),
            "api_secret": "*****",
            "url": "https://attacker.example.com",
        }
        resp = client.post(
            "/admin/video/loungemesh/test/",
            data=json.dumps(req_data),
            content_type="application/json",
        )
        assert resp.status_code == 400
        resp_data = resp.json()
        assert resp_data["ok"] is False
        assert "Target URL does not match" in resp_data["message"]

        # Malformed server_id
        req_data = {
            "server_id": "not-a-valid-uuid",
            "api_secret": "*****",
            "url": server.url,
        }
        resp = client.post(
            "/admin/video/loungemesh/test/",
            data=json.dumps(req_data),
            content_type="application/json",
        )
        assert resp.status_code == 404

        # Reusing stored secret with use_stored_secret=True (unchanged mask)
        with (
            patch(
                "eventyay.control.views.admin_views.test_loungemesh_server_connection",
                return_value=(True, "ok"),
            ) as mock_conn
        ):
            req_data = {
                "server_id": str(server.pk),
                "api_secret": "",
                "use_stored_secret": True,
                "url": server.url,
            }
            resp = client.post(
                "/admin/video/loungemesh/test/",
                data=json.dumps(req_data),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
            assert mock_conn.call_args[0][1] == server.api_secret

        # Explicit replacement secret ending in five asterisks is treated literally
        with (
            patch(
                "eventyay.control.views.admin_views.test_loungemesh_server_connection",
                return_value=(True, "ok"),
            ) as mock_conn
        ):
            req_data = {
                "server_id": str(server.pk),
                "api_secret": "replacement*****",
                "use_stored_secret": False,
                "url": server.url,
            }
            resp = client.post(
                "/admin/video/loungemesh/test/",
                data=json.dumps(req_data),
                content_type="application/json",
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
            assert mock_conn.call_args[0][1] == "replacement*****"


@pytest.mark.django_db
def test_event_duration_access_control(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]
    server = test_setup["server"]

    now = timezone.now()

    # 1. Past event: Host allowed, attendee blocked with 'ended'
    event.date_from = now - timedelta(days=5)
    event.date_to = now - timedelta(days=1)
    event.save()

    assert is_event_accessible_for_role(event, "host")[0] is True
    acc, reason = is_event_accessible_for_role(event, "attendee")
    assert acc is False
    assert reason == "ended"

    assert issue_join_url(event, room, user, role="attendee", server=server) is None
    assert issue_join_url(event, room, user, role="host", server=server) is not None

    # 2. Future event: Host allowed, attendee blocked with 'not_started'
    event.date_from = now + timedelta(days=1)
    event.date_to = now + timedelta(days=2)
    event.save()

    assert is_event_accessible_for_role(event, "host")[0] is True
    acc, reason = is_event_accessible_for_role(event, "attendee")
    assert acc is False
    assert reason == "not_started"

    assert issue_join_url(event, room, user, role="attendee", server=server) is None
    assert issue_join_url(event, room, user, role="host", server=server) is not None

    # 3. Ongoing event: Host and attendee both allowed
    event.date_from = now - timedelta(hours=1)
    event.date_to = now + timedelta(hours=2)
    event.save()

    assert is_event_accessible_for_role(event, "host")[0] is True
    assert is_event_accessible_for_role(event, "attendee")[0] is True

    assert issue_join_url(event, room, user, role="attendee", server=server) is not None
    assert issue_join_url(event, room, user, role="host", server=server) is not None

    # 4. Grant exp bounding for attendee
    grant = issue_signed_grant(event, room, user, role="attendee", server=server, expires_in_seconds=86400)
    payload = jwt.decode(grant, server.api_secret, algorithms=["HS256"], audience="loungemesh")
    assert payload["exp"] == int(event.date_to.timestamp())


@pytest.mark.django_db
def test_websocket_room_url_duration_checks(test_setup, monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]

    room_cache = {str(room.id): room}
    consumer = DummyConsumer(
        user=user,
        world=event,
        permissions=[
            Permission.ROOM_LOUNGEMESH_JOIN.value,
            Permission.ROOM_UPDATE.value,
            Permission.EVENT_UPDATE.value,
        ],
        room_cache=room_cache,
    )
    consumer.event.has_permission_async = AsyncMock(return_value=True)
    module = LoungeMeshModule(consumer)

    def sync_to_async_mock(fn):
        async def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    from django.db import connections
    main_conn = connections["default"]

    now = timezone.now()

    with (
        patch.object(connections.__class__, "__getitem__", return_value=main_conn),
        patch("channels.db.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.decorators.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.modules.loungemesh.database_sync_to_async", sync_to_async_mock),
        patch.object(room, "refresh_from_db_if_outdated", new_callable=AsyncMock),
    ):
        async def run_checks():
            # Future event: attendee gets ConsumerException loungemesh.event_not_started
            event.date_from = now + timedelta(days=1)
            event.date_to = now + timedelta(days=2)
            event.save()

            consumer.is_organizer = False
            with pytest.raises(ConsumerException) as exc_info:
                await module.room_url({"room": str(room.id)})
            assert exc_info.value.code == "loungemesh.event_not_started"

            # Past event: attendee gets ConsumerException loungemesh.event_ended
            event.date_from = now - timedelta(days=2)
            event.date_to = now - timedelta(days=1)
            event.save()

            with pytest.raises(ConsumerException) as exc_info:
                await module.room_url({"room": str(room.id)})
            assert exc_info.value.code == "loungemesh.event_ended"

            # Host in organizer area with active session-bound StaffSession can access past event
            from eventyay.base.models.auth import StaffSession

            admin_user = test_setup["admin_user"]
            consumer.is_organizer = True
            consumer.platform_user = admin_user
            consumer.session_key = "duration-host-session"
            StaffSession.objects.create(user=admin_user, session_key="duration-host-session")
            fake_url = f"http://localhost:8780/join/lms-{event.slug}-{room.id}?grant=hostgrant"
            with patch.object(module, "_get_join_url", new_callable=AsyncMock, return_value=fake_url):
                await module.room_url({"room": str(room.id)})
                assert consumer.sent_data["role"] == "host"
                assert consumer.sent_data["url"] == fake_url

        asyncio.run(run_checks())


@pytest.mark.django_db
def test_loungemesh_security_improvements(test_setup):
    event = test_setup["event"]
    user = test_setup["user"]
    room = test_setup["room"]
    server = test_setup["server"]

    # 1. Grant lifetime default (300s) and single_user claims
    grant = issue_signed_grant(event, room, user, role="attendee", server=server)
    payload = jwt.decode(grant, server.api_secret, algorithms=["HS256"], audience="loungemesh")
    now_ts = int(time.time())
    assert payload["exp"] <= now_ts + 301
    assert payload["single_user"] is True
    assert payload["singleUser"] is True

    # 2. VIDEO_SERVER_ALLOW_PRIVATE_HOSTS setting check
    with override_settings(VIDEO_SERVER_ALLOW_PRIVATE_HOSTS=False):
        valid, msg = validate_loungemesh_server_url("http://192.168.1.5:8000")
        assert valid is False
        assert "private" in str(msg).lower() or "https://" in str(msg).lower()

    # 3. Connection error sanitization (no str(e) leakage)
    ssl_err = requests.exceptions.SSLError("secret internal socket /dev/ssl error")
    with patch("requests.Session.get", side_effect=ssl_err):
        ok, msg = svc_test_loungemesh_server_connection("http://localhost:8780", "secret123")
        assert ok is False
        assert "secret internal socket" not in str(msg)
        assert "SSL certificate verification failed" in str(msg)

    # 4. Pinned connection adapter verification (assert actual socket connection address)
    from eventyay.base.services.loungemesh import PinnedIPAdapter

    pinned_target_ip = "93.184.216.34"
    adapter = PinnedIPAdapter(pinned_target_ip)
    assert adapter.pinned_ip == pinned_target_ip

    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    connected_socket_addrs = []

    def mock_create_connection(address, *args, **kwargs):
        connected_socket_addrs.append(address)
        raise OSError("Mock connection abort")

    with patch("urllib3.util.connection.create_connection", side_effect=mock_create_connection):
        try:
            s.get("https://rebinding-victim.example.com/api/test", timeout=1)
        except Exception:
            pass

    assert len(connected_socket_addrs) == 1
    assert connected_socket_addrs[0] == (pinned_target_ip, 443)

    # 5. Embed origins respects settings.DEBUG
    with override_settings(DEBUG=False):
        # In DEBUG=False, neither localhost:8780 nor loungemesh.com should appear unless in DB
        LoungeMeshServer.objects.all().delete()
        origins = loungemesh_embed_origins()
        assert "http://localhost:8780" not in origins
        assert "https://loungemesh.com" not in origins

    # 6. Admin vs Custom server deletion & duplicate/cap enforcement
    with scope(event=event):
        # Admin-created server (is_user_managed=False)
        admin_srv = LoungeMeshServer.objects.create(
            url="https://admin-lms.example.com",
            api_secret="secret",
            event_exclusive=event,
            is_user_managed=False,
        )
        # Room-editor created server (is_user_managed=True)
        user_srv = LoungeMeshServer.objects.create(
            url="https://user-lms.example.com",
            api_secret="secret",
            event_exclusive=event,
            is_user_managed=True,
        )

        consumer = DummyConsumer(user=user, world=event)
        module = LoungeMeshModule(consumer)

        # Organizer cannot delete admin-created server
        assert module._delete_custom_server(admin_srv.id) is False
        assert LoungeMeshServer.objects.filter(pk=admin_srv.id).exists()

        # Organizer can delete room-editor user-managed server
        assert module._delete_custom_server(user_srv.id) is True
        assert not LoungeMeshServer.objects.filter(pk=user_srv.id).exists()

        # Duplicate check
        dup_res = module._check_server_limit_and_duplicate("https://admin-lms.example.com")
        assert dup_res is not None
        assert dup_res[0] == "loungemesh.duplicate_server"

        # Cap limit check
        for i in range(4):
            LoungeMeshServer.objects.create(
                url=f"https://extra-{i}.example.com",
                api_secret="sec",
                event_exclusive=event,
                is_user_managed=True,
            )
        cap_res = module._check_server_limit_and_duplicate("https://brand-new.example.com")
        assert cap_res is not None
        assert cap_res[0] == "loungemesh.limit_reached"


@pytest.mark.django_db
def test_loungemesh_room_settings_host_only(test_setup):
    import jwt

    from eventyay.base.services.loungemesh import issue_signed_grant
    from eventyay.base.services.room import MODERATED_CALL_MODULE_PERMISSIONS

    event = test_setup["event"]
    server = test_setup["server"]
    user = test_setup["user"]

    # LoungeMesh call modules are not in MODERATED_CALL_MODULE_PERMISSIONS:
    # only hosts with ROOM_UPDATE or EVENT_UPDATE can modify room settings
    assert "call.loungemesh" not in MODERATED_CALL_MODULE_PERMISSIONS
    assert "channel.loungemesh" not in MODERATED_CALL_MODULE_PERMISSIONS

    # When feature flags are toggled off in room_cfg, grant accurately reflects them
    class MockRoom:
        pk = 99
        module_config = [
            {
                "type": "call.loungemesh",
                "config": {
                    "enable_notes": False,
                    "enable_whiteboard": False,
                    "enable_spatial_chat": False,
                },
            }
        ]

    token = issue_signed_grant(event, MockRoom(), user, "host", server=server)
    claims = jwt.decode(token, server.api_secret, algorithms=["HS256"], audience="loungemesh")
    assert claims["features"] == {
        "notes": False,
        "whiteboard": False,
        "spatial_chat": False,
    }


@pytest.mark.django_db
def test_loungemesh_session_bound_host_and_verified_identity(test_setup, monkeypatch):
    from types import SimpleNamespace
    from urllib.parse import parse_qs, urlparse

    import jwt

    from eventyay.base.models import Team
    from eventyay.base.models.auth import StaffSession
    from eventyay.base.services.user import encode_email
    from eventyay.features.live.modules.auth import AuthModule

    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

    organizer = test_setup["organizer"]
    event = test_setup["event"]
    room = test_setup["room"]
    server = test_setup["server"]
    server.active = True
    server.save()

    # Ensure event has live trait_grants so AuthModule login succeeds cleanly
    if not event.trait_grants:
        event.trait_grants = {}
    event.save()

    staff_mod = User.objects.create(
        email="staffmod@example.com",
        fullname="Staff Moderator",
        is_staff=True,
        is_superuser=False,
    )
    mod_team = Team.objects.create(
        organizer=organizer,
        name="Video Moderators",
        all_events=True,
        can_video_moderate=True,
        can_video_manage_content=False,
    )
    mod_team.members.add(staff_mod)

    staff_other = User.objects.create(
        email="staffother@example.com",
        fullname="Staff Non-Video",
        is_staff=True,
        is_superuser=False,
    )
    other_team = Team.objects.create(
        organizer=organizer,
        name="Items Team",
        all_events=True,
        can_change_items=True,
    )
    other_team.members.add(staff_other)

    admin_session = StaffSession.objects.create(
        user=staff_mod,
        session_key="sess-admin-active",
    )
    other_admin_session = StaffSession.objects.create(
        user=staff_other,
        session_key="sess-other-admin",
    )

    class LiveSessionConsumer:
        def __init__(self, platform_user, session_key, query_string=b"organizer=1"):
            self.event = event
            self.user = None
            self.platform_user = None
            self.platform_user_id = None
            self.session_key = None
            self.is_organizer = False
            self.socket_id = f"sock-{session_key or 'anon'}"
            self.channel_name = f"chan-{session_key or 'anon'}"
            self.room_cache = {str(room.id): room}
            self.channel_cache = {}
            self.known_room_id_cache = set()
            self.scope = {
                "user": platform_user,
                "session": SimpleNamespace(session_key=session_key),
                "query_string": query_string,
            }
            self.channel_layer = SimpleNamespace(
                group_add=AsyncMock(),
                send=AsyncMock(),
            )
            self.sent_data = None
            self.sent_messages = []

        async def send_json(self, payload):
            self.sent_messages.append(payload)

        async def send_error(self, code=None, message=None):
            raise AssertionError(f"Unexpected consumer error: {code} - {message}")

        async def send_success(self, data):
            self.sent_data = data
            return data

    def sync_to_async_mock(fn):
        async def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    def extract_grant_claims(url_str):
        qs = parse_qs(urlparse(url_str).query)
        return jwt.decode(qs["grant"][0], server.api_secret, algorithms=["HS256"], audience="loungemesh")

    from django.db import connections
    main_conn = connections["default"]

    class DummyRedis:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def hgetall(self, key):
            return {}

        async def eval(self, *args):
            return []

    with (
        patch.object(connections.__class__, "__getitem__", return_value=main_conn),
        patch("channels.db.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.base.models.event.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.base.models.auth.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.base.models.cache.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.decorators.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.modules.auth.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.modules.loungemesh.database_sync_to_async", sync_to_async_mock),
        patch("eventyay.features.live.modules.auth.aredis", return_value=DummyRedis()),
        patch("eventyay.features.live.modules.auth.register_user_connection", new_callable=AsyncMock),
        patch("eventyay.features.live.modules.auth.get_user_connection_count", new_callable=AsyncMock, return_value=1),
        patch("eventyay.base.services.chat.ChatService.enforce_forced_joins", new_callable=AsyncMock),
        patch.object(room, "refresh_from_db_if_outdated", new_callable=AsyncMock),
    ):
        async def run_scenarios():
            # --- Scenario A: Two sessions for the same staff moderator ---
            # 1. Authenticate Session 1 (admin mode active)
            c_admin = LiveSessionConsumer(staff_mod, "sess-admin-active")
            await AuthModule(c_admin).login({"is_organizer": True})
            assert c_admin.platform_user_id == staff_mod.pk
            assert c_admin.session_key == "sess-admin-active"
            assert "admin" in c_admin.user.traits

            # 2. Authenticate Session 2 (regular browser session, no StaffSession)
            c_regular = LiveSessionConsumer(staff_mod, "sess-regular-browser")
            await AuthModule(c_regular).login({"is_organizer": True})
            assert c_regular.platform_user_id == staff_mod.pk
            assert c_regular.session_key == "sess-regular-browser"

            # Force stale 'admin' trait onto DB video user row to simulate cross-session / pre-stop trait state
            with scope(event=event):
                vuser = User.objects.get(pk=c_admin.user.pk)
                if "admin" not in (vuser.traits or []):
                    vuser.traits = list(vuser.traits or []) + ["admin"]
                    vuser.save(update_fields=["traits"])
                c_admin.user.refresh_from_db()
                c_regular.user.refresh_from_db()

            # Session 1 receives host grant while admin mode is active
            await LoungeMeshModule(c_admin).room_url({"room": str(room.id)})
            assert c_admin.sent_data["role"] == "host"
            assert extract_grant_claims(c_admin.sent_data["url"])["role"] == "host"

            # Session 2 MUST remain moderator (never elevated to host by Session 1 or stored 'admin' trait)
            await LoungeMeshModule(c_regular).room_url({"room": str(room.id)})
            assert c_regular.sent_data["role"] == "moderator"
            assert extract_grant_claims(c_regular.sent_data["url"])["role"] == "moderator"

            # End admin mode in Session 1 (DB video user still has 'admin' trait)
            admin_session.date_end = timezone.now()
            admin_session.save(update_fields=["date_end"])

            # Subsequent grant issuance on Session 1's existing connection MUST drop back to moderator
            await LoungeMeshModule(c_admin).room_url({"room": str(room.id)})
            assert c_admin.sent_data["role"] == "moderator"
            assert extract_grant_claims(c_admin.sent_data["url"])["role"] == "moderator"

            # --- Scenario B: Non-moderator staff account across two sessions ---
            c_other_admin = LiveSessionConsumer(staff_other, "sess-other-admin")
            await AuthModule(c_other_admin).login({"is_organizer": True})
            await LoungeMeshModule(c_other_admin).room_url({"room": str(room.id)})
            assert c_other_admin.sent_data["role"] == "host"

            c_other_regular = LiveSessionConsumer(staff_other, "sess-other-regular")
            await AuthModule(c_other_regular).login({"is_organizer": True})
            assert c_other_regular.is_organizer is True
            assert "admin" not in c_other_regular.user.traits
            await LoungeMeshModule(c_other_regular).room_url({"room": str(room.id)})
            assert c_other_regular.sent_data["role"] == "attendee"

            other_admin_session.date_end = timezone.now()
            other_admin_session.save(update_fields=["date_end"])
            await LoungeMeshModule(c_other_admin).room_url({"room": str(room.id)})
            assert c_other_admin.sent_data["role"] == "attendee"

            # --- Scenario C: Token login without verified platform account binding ---
            # Even with an :orga token whose uid matches staff_mod's email hash and admin trait,
            # and even if an unrelated Django session exists on the WebSocket scope,
            # token-authenticated connections must NOT fall back to scope user/session and must withhold elevation.
            uid = encode_email(staff_mod.email)
            decoded_token = {
                "uid": uid,
                "traits": ["admin", f"eventyay-video-event-{event.slug}-organizer"],
            }
            StaffSession.objects.create(user=staff_other, session_key="sess-active-token-scope")
            c_token = LiveSessionConsumer(staff_other, "sess-active-token-scope")
            with patch.object(event, "decode_token", return_value=decoded_token):
                await AuthModule(c_token).login({"token": "fake.jwt.token", "is_organizer": True})
            assert c_token.platform_user_id is None
            assert c_token.session_key is None
            assert c_token.platform_auth_checked is True
            assert c_token.is_organizer is True
            # Note: token-authenticated :orga consumer may pass room_action via traits,
            # but LoungeMesh grant issuer must strictly withhold host/moderator elevation!
            c_token.event = event
            with patch.object(event, "has_permission_async", new_callable=AsyncMock, return_value=True):
                await LoungeMeshModule(c_token).room_url({"room": str(room.id)})
            assert c_token.sent_data["role"] == "attendee"
            assert extract_grant_claims(c_token.sent_data["url"])["role"] == "attendee"

        asyncio.run(run_scenarios())

