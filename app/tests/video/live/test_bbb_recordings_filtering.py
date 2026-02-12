
import re
import uuid
from contextlib import asynccontextmanager

import pytest
from aioresponses import aioresponses
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from venueless.core.models import BBBServer, User
from venueless.routing import application



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
            ["user.update", 123, {"profile": {"display_name": "Recording Viewer"}}]
        )
        await communicator.receive_json_from()
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_filters_unpublished(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 456, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-published</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/playback.html?meetingid=rec-published</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-unpublished</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>3</participants>
            <state>unpublished</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/playback.html?meetingid=rec-unpublished</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert response[2]["results"]
            # Only published recording should be returned
            assert len(response[2]["results"]) == 1
            assert response[2]["results"][0]["state"] == "published"
            assert response[2]["results"][0]["participants"] == 2


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_filters_deleted(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 457, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-published</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/playback.html?meetingid=rec-pub</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-deleted</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>3</participants>
            <state>deleted</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/playback.html?meetingid=rec-del</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 1
            assert response[2]["results"][0]["state"] == "published"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_returns_only_published(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 458, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-1</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-1</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-2</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>5</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>video</type>
                    <url>https://video1.pretix.eu/playback/video/rec-2</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 2
            assert all(rec["state"] == "published" for rec in response[2]["results"])
            assert response[2]["results"][0]["participants"] == 2
            assert response[2]["results"][1]["participants"] == 5


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_filters_processing(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 459, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-processing</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>processing</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/processing</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert response[2]["results"] == []


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_case_insensitive_state_check(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 460, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-1</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>PUBLISHED</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-1</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-2</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>3</participants>
            <state>Published</state>
            <playback>
                <format>
                    <type>video</type>
                    <url>https://video1.pretix.eu/playback/video/rec-2</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-3</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609473200000</startTime>
            <endTime>1609476800000</endTime>
            <participants>4</participants>
            <state>unpublished</state>
            <playback>
                <format>
                    <type>video</type>
                    <url>https://video1.pretix.eu/playback/video/rec-3</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            # Should handle PUBLISHED and Published as valid, unpublished as invalid
            assert len(response[2]["results"]) == 2
            assert all(rec["state"] in ("PUBLISHED", "Published") for rec in response[2]["results"])


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_missing_state_element(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 461, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-published</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-pub</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-malformed</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>3</participants>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-no-state</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 1
            assert response[2]["results"][0]["state"] == "published"
            assert response[2]["results"][0]["participants"] == 2


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_mixed_states(bbb_room):
    """Test filtering with mixed recording states (published, unpublished, deleted, processing)."""
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 462, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-pub-1</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-1</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-unpub</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <participants>3</participants>
            <state>unpublished</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-unpub</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-deleted</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609473200000</startTime>
            <endTime>1609476800000</endTime>
            <participants>1</participants>
            <state>deleted</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-del</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-processing</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609480000000</startTime>
            <endTime>1609483600000</endTime>
            <participants>4</participants>
            <state>processing</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-proc</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-pub-2</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609487200000</startTime>
            <endTime>1609490800000</endTime>
            <participants>5</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>video</type>
                    <url>https://video1.pretix.eu/playback/video/rec-2</url>
                </format>
            </playback>
       </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 2
            assert all(rec["state"] == "published" for rec in response[2]["results"])
            assert response[2]["results"][0]["participants"] == 2
            assert response[2]["results"][1]["participants"] == 5


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_empty_list(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 463, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings/>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert response[2]["results"] == []


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_missing_required_fields(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 464, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-valid</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-valid</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-missing-participants</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609466000000</startTime>
            <endTime>1609469600000</endTime>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-missing-participants</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-missing-start</recordID>
            <meetingID>meeting-123</meetingID>
            <endTime>1609476800000</endTime>
            <participants>3</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-missing-start</url>
                </format>
            </playback>
        </recording>
        <recording>
            <recordID>rec-missing-end</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609480000000</startTime>
            <participants>4</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video1.pretix.eu/playback/presentation/2.0/rec-missing-end</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 1
            assert response[2]["results"][0]["participants"] == 2


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_malformed_xml(bbb_room):
    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 465, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<response><returncode>SUCCESS</returncode><recordings><recording>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert response[2]["results"] == []


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_recordings_mixed_server_success(bbb_room):
    await database_sync_to_async(BBBServer.objects.create)(
        url="https://video2.pretix.eu/bigbluebutton/",
        secret="bogussecret2",
        active=True,
    )

    with aioresponses() as m:
        async with world_communicator(named=True) as c:
            await c.send_json_to(["bbb.recordings", 466, {"room": str(bbb_room.pk)}])

            m.get(
                re.compile(r"^https://video1.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                status=500,
            )
            m.get(
                re.compile(r"^https://video2.pretix.eu/bigbluebutton/api/getRecordings.*$"),
                body="""<?xml version="1.0"?>
<response>
    <returncode>SUCCESS</returncode>
    <recordings>
        <recording>
            <recordID>rec-valid</recordID>
            <meetingID>meeting-123</meetingID>
            <startTime>1609459200000</startTime>
            <endTime>1609462800000</endTime>
            <participants>2</participants>
            <state>published</state>
            <playback>
                <format>
                    <type>presentation</type>
                    <url>https://video2.pretix.eu/playback/presentation/2.0/rec-valid</url>
                </format>
            </playback>
        </recording>
    </recordings>
</response>""",
            )

            response = await c.receive_json_from()
            assert response[0] == "success"
            assert len(response[2]["results"]) == 1
            assert response[2]["results"][0]["participants"] == 2