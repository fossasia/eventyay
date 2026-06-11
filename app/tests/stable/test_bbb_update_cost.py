from unittest.mock import Mock

import pytest
import requests
from django.core.management import call_command

from eventyay.base.management.commands.bbb_update_cost import REQUEST_TIMEOUT
from eventyay.base.models import BBBServer


SUCCESS_NO_MEETINGS = """
<response>
  <returncode>SUCCESS</returncode>
  <meetings />
</response>
"""

SUCCESS_WITH_MEETING = """
<response>
  <returncode>SUCCESS</returncode>
  <meetings>
    <meeting>
      <participantCount>4</participantCount>
      <voiceParticipantCount>2</voiceParticipantCount>
      <videoCount>1</videoCount>
    </meeting>
  </meetings>
</response>
"""


class InlinePool:
    def __init__(self, processes):
        self.processes = processes

    def map(self, function, servers):
        return [function(server) for server in servers]


def response_with(text):
    response = Mock(text=text)
    response.raise_for_status.return_value = None
    return response


@pytest.mark.django_db
def test_bbb_update_cost_resets_idle_server_cost(mocker):
    server = BBBServer.objects.create(
        url="https://idle.example.com/bigbluebutton/",
        secret="secret",
        cost=99,
    )
    mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.pool.ThreadPool",
        InlinePool,
    )
    request = mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.requests.get",
        return_value=response_with(SUCCESS_NO_MEETINGS),
    )

    call_command("bbb_update_cost")

    server.refresh_from_db()
    assert server.cost == 0
    request.assert_called_once()
    assert request.call_args.kwargs["timeout"] == REQUEST_TIMEOUT


@pytest.mark.django_db
def test_bbb_update_cost_calculates_meeting_cost(mocker):
    server = BBBServer.objects.create(
        url="https://busy.example.com/bigbluebutton/",
        secret="secret",
    )
    mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.pool.ThreadPool",
        InlinePool,
    )
    mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.requests.get",
        return_value=response_with(SUCCESS_WITH_MEETING),
    )

    call_command("bbb_update_cost")

    server.refresh_from_db()
    assert server.cost == 58


@pytest.mark.django_db
def test_bbb_update_cost_ignores_inactive_and_continues_after_failure(mocker):
    failed = BBBServer.objects.create(
        url="https://failed.example.com/bigbluebutton/",
        secret="secret",
        cost=12,
    )
    healthy = BBBServer.objects.create(
        url="https://healthy.example.com/bigbluebutton/",
        secret="secret",
        cost=12,
    )
    inactive = BBBServer.objects.create(
        url="https://inactive.example.com/bigbluebutton/",
        secret="secret",
        active=False,
        cost=12,
    )

    def get(url, timeout):
        assert timeout == REQUEST_TIMEOUT
        if "failed.example.com" in url:
            raise requests.ConnectionError
        return response_with(SUCCESS_NO_MEETINGS)

    mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.pool.ThreadPool",
        InlinePool,
    )
    request = mocker.patch(
        "eventyay.base.management.commands.bbb_update_cost.requests.get",
        side_effect=get,
    )

    call_command("bbb_update_cost")

    failed.refresh_from_db()
    healthy.refresh_from_db()
    inactive.refresh_from_db()
    assert failed.cost == 12
    assert healthy.cost == 0
    assert inactive.cost == 12
    assert request.call_count == 2
