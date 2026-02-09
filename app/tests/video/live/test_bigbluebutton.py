import re
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse, parse_qs

import pytest
from aiohttp.http_exceptions import HttpProcessingError
from aioresponses import aioresponses
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from venueless.core.models import User
from venueless.routing import application


BBB_CREATE_URL_RE = re.compile(r"^https://video1\.pretix\.eu/bigbluebutton/api/create.*$")
BBB_JOIN_URL_RE = re.compile(r"^https://video1\.pretix\.eu/bigbluebutton/api/join.*$")

@asynccontextmanager
async def world_communicator(named=True):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    communicator.context = response[1]
    assert "world.config" in response[1], response
    if named:
        await communicator.send_json_to(
            ["user.update", 123, {"profile": {"display_name": "Foo Fighter"}}]
        )
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_settings_not_disclosed(bbb_room):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    await communicator.send_json_to(["authenticate", {"client_id": str(uuid.uuid4())}])
    response = await communicator.receive_json_from()
    assert response[0] == "authenticated", response
    assert "bbb_defaults" not in response[1]["world.config"]["world"]
    for room in response[1]["world.config"]["rooms"]:
        if room["id"] == str(bbb_room.id):
            assert room["modules"][0]["type"] == "call.bigbluebutton"
            assert room["modules"][0]["config"] == {}
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_login_required(bbb_room):
    communicator = WebsocketCommunicator(application, "/ws/world/sample/")
    await communicator.connect()
    try:
        await communicator.send_json_to(
            ["bbb.room_url", 123, {"room": str(bbb_room.pk)}]
        )
        response = await communicator.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.unauthenticated"
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_command():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.bla", 123, {"room": "room_0"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.unsupported_command"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_wrong_room(chat_room):
    async with world_communicator() as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(chat_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unknown_room():
    async with world_communicator() as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": "a"}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "room.unknown"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_unnamed(bbb_room):
    async with world_communicator(named=False) as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "bbb.join.missing_profile"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_missing_permission(bbb_room):
    bbb_room.trait_grants = {"participant": ["foo"]}
    await database_sync_to_async(bbb_room.save)()
    async with world_communicator(named=False) as c:
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_silenced(bbb_room):
    await database_sync_to_async(bbb_room.save)()
    async with world_communicator(named=False) as c:
        user = await database_sync_to_async(User.objects.get)()
        user.moderation_state = User.ModerationState.SILENCED
        await database_sync_to_async(user.save)()
        await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])
        response = await c.receive_json_from()
        assert response[0] == "error"
        assert response[2]["code"] == "protocol.denied"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_down(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                status=500,
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_exception(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.id)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                exception=HttpProcessingError(),
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_xml_error(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                body="""<response>
<returncode>FAILED</returncode>
<messageKey>checksumError</messageKey>
<message>You did not pass the checksum security check</message>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "error"
            assert response[2]["code"] == "bbb.failed"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_successful_url(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>6c58284d0c68af95</meetingID>
<internalMeetingID>322ed97cafe9a92fa4ef7f7c70da553f213df06b-1587484839039</internalMeetingID>
<parentMeetingID>bbb-none</parentMeetingID>
<attendeePW>d35746f043310256</attendeePW>
<moderatorPW>bf889e3c60742bee</moderatorPW>
<createTime>1587484839039</createTime>
<voiceBridge>70957</voiceBridge>
<dialNumber>613-555-1234</dialNumber>
<createDate>Tue Apr 21 18:00:39 CEST 2020</createDate>
<hasUserJoined>true</hasUserJoined>
<duration>0</duration>
<hasBeenForciblyEnded>false</hasBeenForciblyEnded>
<messageKey>duplicateWarning</messageKey>
<message>
This conference was already in existence and may currently be in progress.
</message>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert "/join?" in response[2]["url"]

            @database_sync_to_async
            def get_call():
                return bbb_room.bbb_call

            assert (await get_call()).attendee_pw in response[2]["url"]


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_successful_url_moderator(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await database_sync_to_async(bbb_room.role_grants.create)(
                user=await database_sync_to_async(User.objects.get)(),
                world=bbb_room.world,
                role="speaker",
            )
            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton.*$"),
                body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>6c58284d0c68af95</meetingID>
<internalMeetingID>322ed97cafe9a92fa4ef7f7c70da553f213df06b-1587484839039</internalMeetingID>
<parentMeetingID>bbb-none</parentMeetingID>
<attendeePW>d35746f043310256</attendeePW>
<moderatorPW>bf889e3c60742bee</moderatorPW>
<createTime>1587484839039</createTime>
<voiceBridge>70957</voiceBridge>
<dialNumber>613-555-1234</dialNumber>
<createDate>Tue Apr 21 18:00:39 CEST 2020</createDate>
<hasUserJoined>true</hasUserJoined>
<duration>0</duration>
<hasBeenForciblyEnded>false</hasBeenForciblyEnded>
<messageKey>duplicateWarning</messageKey>
<message>
This conference was already in existence and may currently be in progress.
</message>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert "/join?" in response[2]["url"]

            @database_sync_to_async
            def get_call():
                return bbb_room.bbb_call

            assert (await get_call()).moderator_pw in response[2]["url"]

def assert_bbb_params(url, expected_params, present=True):
    parsed = urlparse(str(url))
    params = parse_qs(parsed.query)
    for param, expected_value in expected_params.items():
        if present:
            assert params.get(param) == expected_value
        else:
            assert params.get(param) in (None, ["false"])

def make_bbb_callback(expected_params=None, present=True, body=None, status=200):
    if body is None:
        body = "<response><returncode>SUCCESS</returncode></response>"

    def _cb(url, **kwargs):
        if expected_params:
            assert_bbb_params(url, expected_params, present=present)
        return {"status": status, "body": body}

    return _cb

@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("enabled", (True, False))
@pytest.mark.parametrize(
    "config_key,expected_param",
    (
        ("bbb_mute_on_start", "muteOnStart"),
        ("bbb_disable_cam", "lockSettingsDisableCam"),
        ("bbb_disable_chat", "lockSettingsDisablePublicChat"),
    ),
)
async def test_bbb_create_params_enabled(bbb_room, config_key, expected_param, enabled):
    module = bbb_room.module_config[0]
    if enabled:
        module["config"][config_key] = True
    else:
        module["config"].pop(config_key, None)
    await database_sync_to_async(bbb_room.save)()

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            m.get(
                BBB_CREATE_URL_RE,
                callback=make_bbb_callback({expected_param: ["true"]}, present=enabled, body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>dummy-meeting</meetingID>
<attendeePW>dummy-attendee</attendeePW>
<moderatorPW>dummy-moderator</moderatorPW>
</response>"""),
            )
            m.get(BBB_JOIN_URL_RE, body="""<response><returncode>SUCCESS</returncode></response>""",
            )

            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])
            response = await c.receive_json_from()

            assert response[0] == "success"

@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_waiting_room_sets_guest_policy_and_guest_flag(bbb_room):
    module = bbb_room.module_config[0]
    module["config"]["waiting_room"] = True
    await database_sync_to_async(bbb_room.save)()

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            m.get(
                BBB_CREATE_URL_RE,
                callback=make_bbb_callback({"guestPolicy": ["ASK_MODERATOR"]}, present=True, body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>dummy-meeting</meetingID>
<attendeePW>dummy-attendee</attendeePW>
<moderatorPW>dummy-moderator</moderatorPW>
</response>"""),
            )
            m.get(
                BBB_JOIN_URL_RE,
                callback=make_bbb_callback({"guest": ["true"]}, present=True, body="<response><returncode>SUCCESS</returncode></response>"),
            )

            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])
            response = await c.receive_json_from()

            assert response[0] == "success"

@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize(
    "config_key,expected_params",
    (
        (
            "auto_microphone",
            {
                "userdata-bbb_listen_only_mode": ["false"],
            },
        ),
        (
            "auto_camera",
            {
                "userdata-bbb_auto_share_webcam": ["true"],
                "userdata-bbb_skip_video_preview": ["true"],
            },
        ),
        (
            "hide_presentation",
            {
                "userdata-bbb_auto_swap_layout": ["true"],
            },
        ),
    ),
)
@pytest.mark.parametrize("enabled", (True, False))
async def test_bbb_join_userdata_flags(bbb_room, config_key, expected_params, enabled):
    module = bbb_room.module_config[0]
    if enabled:
        module["config"][config_key] = True
    else:
        module["config"].pop(config_key, None)
    await database_sync_to_async(bbb_room.save)()

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            m.get(
                BBB_CREATE_URL_RE,
                body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>dummy-meeting</meetingID>
<attendeePW>dummy-attendee</attendeePW>
<moderatorPW>dummy-moderator</moderatorPW>
</response>""",
            )
            m.get(
                BBB_JOIN_URL_RE,
                callback=make_bbb_callback(expected_params, present=enabled, body="<response><returncode>SUCCESS</returncode></response>"),
            )

            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])
            response = await c.receive_json_from()

            assert response[0] == "success"

@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_recording_enabled_sets_record_true(bbb_room):
    module = bbb_room.module_config[0]
    module["config"]["record"] = True
    await database_sync_to_async(bbb_room.save)()

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            m.get(
                BBB_CREATE_URL_RE,
                callback=make_bbb_callback({"record": ["true"]}, present=True, body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>dummy-meeting</meetingID>
<attendeePW>dummy-attendee</attendeePW>
<moderatorPW>dummy-moderator</moderatorPW>
</response>"""),
            )
            m.get(BBB_JOIN_URL_RE, body="<response><returncode>SUCCESS</returncode></response>")

            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])
            response = await c.receive_json_from()

            assert response[0] == "success"

@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_disable_privatechat_enabled(bbb_room):
    bbb_room.event.config["bbb_disable_privatechat"] = True
    await database_sync_to_async(bbb_room.event.save)()

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            m.get(
                BBB_CREATE_URL_RE,
                callback=make_bbb_callback({"lockSettingsDisablePrivateChat": ["true"]}, present=True, body="""<response>
<returncode>SUCCESS</returncode>
<meetingID>dummy-meeting</meetingID>
<attendeePW>dummy-attendee</attendeePW>
<moderatorPW>dummy-moderator</moderatorPW>
</response>"""),
            )
            m.get(BBB_JOIN_URL_RE, body="<response><returncode>SUCCESS</returncode></response>")

            await c.send_json_to(["bbb.room_url", 123, {"room": str(bbb_room.pk)}])
            response = await c.receive_json_from()

            assert response[0] == "success"
