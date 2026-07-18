from unittest.mock import Mock

import pytest
from django.urls import reverse

from eventyay.base.models import BBBCall, BBBServer, Room
from eventyay.base.models.auth import StaffSession


@pytest.mark.django_db
def test_move_bbb_room_ends_meeting_on_source_server(
    event, staff_client, staff_user, mocker
):
    source_server = BBBServer.objects.create(
        url="https://source.example.com/bigbluebutton/",
        secret="source-secret",
    )
    target_server = BBBServer.objects.create(
        url="https://target.example.com/bigbluebutton/",
        secret="target-secret",
    )
    room = Room.objects.create(event=event, name="BBB room")
    call = BBBCall.objects.create(event=event, room=room, server=source_server)
    get_url = mocker.patch(
        "eventyay.control.views.admin_views.get_url",
        return_value="https://source.example.com/end",
    )
    response = Mock()
    request = mocker.patch(
        "eventyay.control.views.admin_views.requests.get", return_value=response
    )
    StaffSession.objects.create(
        user=staff_user,
        session_key=staff_client.session.session_key,
    )

    result = staff_client.post(
        reverse("eventyay_admin:video_admin:bbbserver.moveroom"),
        {"room": room.pk, "server": target_server.pk},
    )

    assert result.status_code == 302
    call.refresh_from_db()
    assert call.server == target_server
    get_url.assert_called_once_with(
        "end",
        {"meetingID": call.meeting_id, "password": call.moderator_pw},
        source_server.url,
        source_server.secret,
    )
    request.assert_called_once_with("https://source.example.com/end", timeout=15)
    response.raise_for_status.assert_called_once_with()
