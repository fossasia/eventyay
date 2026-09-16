from unittest.mock import AsyncMock, patch
import pytest
from channels.db import database_sync_to_async
from eventyay.base.models import BBBServer, JanusServer, JitsiServer, TurnServer
from eventyay.control.forms.server_management import (
    BBBServerForm,
    JanusServerForm,
    JitsiServerForm,
    TurnServerForm,
)
from eventyay.base.services.janus import _janus_websocket
from eventyay.base.services.jitsi import normalize_server_url
from eventyay.base.services.bbb import BBBService


@pytest.mark.django_db
def test_disable_ssl_field_persistence():
    janus = JanusServer.objects.create(url="ws://test-janus:8188", disable_ssl=True)
    jitsi = JitsiServer.objects.create(url="http://test-jitsi.local", disable_ssl=True)
    bbb = BBBServer.objects.create(url="http://test-bbb.local/bigbluebutton/api", secret="sec", disable_ssl=True)
    turn = TurnServer.objects.create(hostname="test-turn.local:3478", auth_secret="sec", disable_ssl=True)

    assert janus.disable_ssl is True
    assert jitsi.disable_ssl is True
    assert bbb.disable_ssl is True
    assert turn.disable_ssl is True


@pytest.mark.django_db
def test_forms_allow_http_when_disable_ssl_checked():
    janus_form = JanusServerForm(data={
        "url": "ws://my-janus-server.local:8188",
        "room_create_key": "secretkey",
        "disable_ssl": True,
        "active": True,
    })
    assert janus_form.is_valid(), janus_form.errors

    jitsi_form = JitsiServerForm(data={
        "url": "http://my-jitsi-server.local",
        "app_id": "eventyay",
        "app_secret": "secret",
        "disable_ssl": True,
        "active": True,
    })
    assert jitsi_form.is_valid(), jitsi_form.errors

    bbb_form = BBBServerForm(data={
        "url": "http://my-bbb-server.local/bigbluebutton/api",
        "secret": "testsecret",
        "disable_ssl": True,
        "active": True,
    })
    assert bbb_form.is_valid(), bbb_form.errors

    turn_form = TurnServerForm(data={
        "hostname": "my-turn-server.local:3478",
        "auth_secret": "testsecret",
        "disable_ssl": True,
        "active": True,
    })
    assert turn_form.is_valid(), turn_form.errors


@pytest.mark.django_db
def test_jitsi_normalize_server_url_http():
    res = normalize_server_url("http://custom-jitsi.local")
    assert res["protocol"] == "http:"
    assert res["url"] == "http://custom-jitsi.local"
    assert res["domain"] == "custom-jitsi.local"


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_janus_websocket_disable_ssl_urls():
    import ssl
    server = await database_sync_to_async(JanusServer.objects.create)(
        url="wss://janus.local/janus-ws", disable_ssl=True
    )
    attempted_calls = []

    def fake_connect(url, **kwargs):
        attempted_calls.append((url, kwargs.get("ssl")))
        cm = AsyncMock()
        cm.__aenter__.side_effect = OSError("Connection refused mock")
        return cm

    with patch("websockets.connect", side_effect=fake_connect):
        try:
            async with _janus_websocket(server):
                pass
        except Exception:
            pass

    urls = [call[0] for call in attempted_calls]
    assert "wss://janus.local/janus-ws" in urls
    assert "ws://janus.local/janus-ws" not in urls
    # Verify unverified SSLContext was used
    ctx = attempted_calls[0][1]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE

    server_local = await database_sync_to_async(JanusServer.objects.create)(
        url="wss://localhost:8188", disable_ssl=True
    )
    attempted_calls.clear()
    with patch("websockets.connect", side_effect=fake_connect):
        try:
            async with _janus_websocket(server_local):
                pass
        except Exception:
            pass

    urls_local = [call[0] for call in attempted_calls]
    assert "wss://localhost:8188" in urls_local
    assert "wss://janus:8188" in urls_local
    assert "ws://janus:8188" not in urls_local
    for _, ssl_arg in attempted_calls:
        assert isinstance(ssl_arg, ssl.SSLContext)


@pytest.mark.asyncio
async def test_bbb_service_disable_ssl():
    bbb_service = BBBService(event=None)
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_cm = AsyncMock()
        mock_get.return_value = mock_cm
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"<response><returncode>SUCCESS</returncode></response>"
        mock_cm.__aenter__.return_value = mock_resp

        res = await bbb_service._get("http://bbb.local/api/create", disable_ssl=True)
        assert res is not False
        _, kwargs = mock_get.call_args
        assert kwargs.get("ssl") is False
