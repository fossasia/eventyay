import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from lxml import etree

from eventyay.base.models import BBBServer, Event
from eventyay.base.services.bbb import BBBService, safe_xpath_text


@pytest.fixture
def event():
    return Event.objects.create(
        name="Test Event",
        slug="test-event",
        date_from="2026-01-01",
        timezone="UTC",
    )


@pytest.fixture
def bbb_server():
    return BBBServer.objects.create(
        url="https://bbb.example.com",
        secret="test-secret",
        active=True,
    )


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_no_call(event):
    room = Mock(event=event, id="room-123")
    service = BBBService(event)

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call:
        mock_get_call.return_value = None
        result = await service.get_recordings_for_room(room)

    assert result == {"recordings": [], "error_type": "NO_RECORDINGS"}


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_empty_list(event, bbb_server):
    room = Mock(event=event, id="room-123")
    call = Mock(meeting_id="meeting-123", server=bbb_server)
    service = BBBService(event)

    xml_response = """<?xml version="1.0"?>
    <response>
        <returncode>SUCCESS</returncode>
        <recordings/>
    </response>
    """

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call, \
         patch.object(service, "_get_possible_servers", new_callable=AsyncMock) as mock_servers, \
         patch.object(service, "_get", new_callable=AsyncMock) as mock_get:
        mock_get_call.return_value = call
        mock_servers.return_value = [bbb_server]
        mock_get.return_value = etree.fromstring(xml_response)

        result = await service.get_recordings_for_room(room)

    assert result["recordings"] == []
    assert result["error_type"] == "NO_RECORDINGS"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_success_with_data(event, bbb_server):
    room = Mock(event=event, id="room-123")
    call = Mock(meeting_id="meeting-123", server=bbb_server)
    service = BBBService(event)

    xml_response = """<?xml version="1.0"?>
    <response>
        <returncode>SUCCESS</returncode>
        <recordings>
            <recording>
                <recordID>rec-1</recordID>
                <meetingID>meeting-123</meetingID>
                <startTime>1609459200000</startTime>
                <endTime>1609462800000</endTime>
                <participants>2</participants>
                <state>available</state>
                <playback>
                    <format>
                        <type>presentation</type>
                        <url>https://bbb.example.com/playback/presentation/2.0/playback.html?meetingid=rec-1</url>
                    </format>
                </playback>
            </recording>
        </recordings>
    </response>
    """

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call, \
         patch.object(service, "_get_possible_servers", new_callable=AsyncMock) as mock_servers, \
         patch.object(service, "_get", new_callable=AsyncMock) as mock_get:
        mock_get_call.return_value = call
        mock_servers.return_value = [bbb_server]
        mock_get.return_value = etree.fromstring(xml_response)

        result = await service.get_recordings_for_room(room)

    assert len(result["recordings"]) == 1
    assert result["error_type"] is None
    assert result["recordings"][0]["participants"] == "2"
    assert result["recordings"][0]["state"] == "available"
    assert "url" in result["recordings"][0]


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_unavailable(event, bbb_server):
    room = Mock(event=event, id="room-123")
    call = Mock(meeting_id="meeting-123", server=bbb_server)
    service = BBBService(event)

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call, \
         patch.object(service, "_get_possible_servers", new_callable=AsyncMock) as mock_servers, \
         patch.object(service, "_get", new_callable=AsyncMock) as mock_get:
        mock_get_call.return_value = call
        mock_servers.return_value = [bbb_server]
        mock_get.return_value = False

        result = await service.get_recordings_for_room(room)

    assert result["recordings"] == []
    assert result["error_type"] == "BBB_UNAVAILABLE"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_exception_handling(event, bbb_server):
    """Test that exceptions during processing are caught and logged."""
    room = Mock(event=event, id="room-123")
    call = Mock(meeting_id="meeting-123", server=bbb_server)
    service = BBBService(event)

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call, \
         patch.object(service, "_get_possible_servers", new_callable=AsyncMock) as mock_servers, \
         patch.object(service, "_get", new_callable=AsyncMock) as mock_get:
        mock_get_call.return_value = call
        mock_servers.return_value = [bbb_server]
        mock_get.side_effect = Exception("Unexpected error")

        result = await service.get_recordings_for_room(room)

    assert result["recordings"] == []
    assert result["error_type"] == "BBB_UNAVAILABLE"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_get_recordings_multiple_servers_with_precedence(event):
    """Test error precedence: if any server returns recordings, success; otherwise prefer BBB_UNAVAILABLE."""
    server1 = BBBServer.objects.create(url="https://bbb1.example.com", secret="secret1", active=True)
    server2 = BBBServer.objects.create(url="https://bbb2.example.com", secret="secret2", active=True)
    
    room = Mock(event=event, id="room-123")
    call = Mock(meeting_id="meeting-123", server=server1)
    service = BBBService(event)

    xml_response = """<?xml version="1.0"?>
    <response>
        <returncode>SUCCESS</returncode>
        <recordings>
            <recording>
                <startTime>1609459200000</startTime>
                <endTime>1609462800000</endTime>
                <participants>2</participants>
                <state>available</state>
                <playback>
                    <format>
                        <type>presentation</type>
                        <url>https://bbb.example.com/rec</url>
                    </format>
                </playback>
            </recording>
        </recordings>
    </response>
    """

    with patch("eventyay.base.services.bbb.get_call_for_room", new_callable=AsyncMock) as mock_get_call, \
         patch.object(service, "_get_possible_servers", new_callable=AsyncMock) as mock_servers, \
         patch.object(service, "_get", new_callable=AsyncMock) as mock_get:
        mock_get_call.return_value = call
        mock_servers.return_value = [server1, server2]
        # First server fails, second succeeds
        mock_get.side_effect = [False, etree.fromstring(xml_response)]

        result = await service.get_recordings_for_room(room)

    # Should succeed because one server returned recordings
    assert len(result["recordings"]) == 1
    assert result["error_type"] is None


def test_safe_xpath_text_success():
    xml = """<?xml version="1.0"?>
    <root>
        <value>test data</value>
    </root>
    """
    element = etree.fromstring(xml)
    result = safe_xpath_text(element, "value")
    assert result == "test data"


def test_safe_xpath_text_missing():
    xml = """<?xml version="1.0"?>
    <root>
        <value>test</value>
    </root>
    """
    element = etree.fromstring(xml)
    result = safe_xpath_text(element, "missing")
    assert result is None


def test_safe_xpath_text_with_default():
    xml = """<?xml version="1.0"?>
    <root>
        <value>test</value>
    </root>
    """
    element = etree.fromstring(xml)
    result = safe_xpath_text(element, "missing", default="default_value")
    assert result == "default_value"


def test_safe_xpath_text_empty_text():
    xml = """<?xml version="1.0"?>
    <root>
        <value/>
    </root>
    """
    element = etree.fromstring(xml)
    result = safe_xpath_text(element, "value")
    assert result is None
