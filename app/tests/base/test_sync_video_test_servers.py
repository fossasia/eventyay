import io

import pytest
from django.core.management import call_command

from eventyay.base.models import BBBServer, JanusServer, JitsiServer, TurnServer


@pytest.mark.django_db
def test_sync_video_test_servers_enable():
    out = io.StringIO()
    call_command("sync_video_test_servers", "--enable", stdout=out)
    output = out.getvalue()

    assert "Enabling Local Video Test Servers" in output
    assert "✓ All local video test servers enabled" in output

    # Check that BBBServer was created and active
    bbb = BBBServer.objects.get(url="https://test-install.blindsidenetworks.com/bigbluebutton/api")
    assert bbb.active is True

    # Check JanusServer
    janus = JanusServer.objects.get(url="ws://localhost:8188")
    assert janus.active is True

    # Check JitsiServer
    jitsi = JitsiServer.objects.get(url="http://localhost:8002")
    assert jitsi.active is True

    # Check TurnServer
    turn = TurnServer.objects.get(hostname="localhost:3478")
    assert turn.active is True


@pytest.mark.django_db
def test_sync_video_test_servers_disable():
    # First enable to populate servers
    call_command("sync_video_test_servers", "--enable")

    # Now disable
    out = io.StringIO()
    call_command("sync_video_test_servers", "--disable", stdout=out)
    output = out.getvalue()

    assert "Deactivating Local Video Test Servers" in output
    assert "Deactivated local servers" in output

    # Check that localhost servers are marked inactive
    assert BBBServer.objects.get(url="https://test-install.blindsidenetworks.com/bigbluebutton/api").active is False
    assert JanusServer.objects.get(url="ws://localhost:8188").active is False
    assert JitsiServer.objects.get(url="http://localhost:8002").active is False
    assert TurnServer.objects.get(hostname="localhost:3478").active is False
