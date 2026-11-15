import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.dispatch import Signal
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base import entitlements
from eventyay.base.entitlements import EntitlementDecision
from eventyay.base.models import Event, Organizer, User
from eventyay.base.models.room import Room, RoomView
from eventyay.base.services.video_entitlements import (
    JITSI_CONCURRENT_ROOMS_CAPABILITY,
    admit_to_jitsi_room,
    running_jitsi_room_ids,
)
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules import jitsi as jitsi_module
from eventyay.features.live.modules.jitsi import JitsiModule


pytestmark = pytest.mark.django_db

JITSI = [{"type": "call.jitsi", "config": {}}]


@pytest.fixture
def room_limit(monkeypatch):
    """Install a policy that limits running Jitsi rooms; returns the limit holder and calls."""
    signal = Signal()
    monkeypatch.setattr(entitlements, "entitlement_check", signal)
    policy = {"limit": 1}
    calls = []

    def receiver(sender, capability, event, quantity=1, **kwargs):
        if capability != JITSI_CONCURRENT_ROOMS_CAPABILITY:
            return None
        calls.append((sender, event, quantity))
        if quantity > policy["limit"]:
            return EntitlementDecision(
                allowed=False,
                reason_code="tier_limit_exceeded",
                limit=policy["limit"],
                message="Room limit reached.",
            )
        return EntitlementDecision(allowed=True, limit=policy["limit"])

    signal.connect(receiver, weak=False)
    return policy, calls


def make_event(organizer, slug):
    return Event.objects.create(
        organizer=organizer, name=slug, slug=slug, date_from=now(), currency="EUR"
    )


def make_room(event, name, **kwargs):
    with scopes_disabled():
        return Room.objects.create(event=event, name=name, module_config=JITSI, **kwargs)


def make_user(email):
    return User.objects.create_user(email=email, password="secret", fullname=email)


def enter(room, user):
    return RoomView.objects.create(room=room, user=user)


@pytest.fixture
def setup():
    organizer = Organizer.objects.create(name="Org", slug="org")
    event = make_event(organizer, "conf")
    return SimpleNamespace(
        organizer=organizer,
        event=event,
        room_a=make_room(event, "A"),
        room_b=make_room(event, "B"),
        alice=make_user("alice@example.com"),
        bob=make_user("bob@example.com"),
        carol=make_user("carol@example.com"),
    )


def test_without_policy_admission_is_allowed_and_recorded(monkeypatch, setup):
    monkeypatch.setattr(entitlements, "entitlement_check", Signal())
    view = enter(setup.room_a, setup.alice)

    assert admit_to_jitsi_room(setup.room_a, setup.alice).allowed

    view.refresh_from_db()
    assert view.jitsi_joined_at is not None
    assert running_jitsi_room_ids(setup.organizer) == {setup.room_a.pk}


def test_starting_a_room_beyond_the_limit_is_denied(room_limit, setup):
    policy, calls = room_limit
    enter(setup.room_a, setup.alice)
    assert admit_to_jitsi_room(setup.room_a, setup.alice).allowed

    bob_view = enter(setup.room_b, setup.bob)
    decision = admit_to_jitsi_room(setup.room_b, setup.bob)

    assert not decision.allowed
    assert decision.reason_code == "tier_limit_exceeded"
    assert calls[-1] == (setup.organizer, setup.event, 2)
    bob_view.refresh_from_db()
    assert bob_view.jitsi_joined_at is None


def test_joining_a_running_room_does_not_need_a_free_room(room_limit, setup):
    policy, calls = room_limit
    enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    checks_before = len(calls)

    bob_view = enter(setup.room_a, setup.bob)
    assert admit_to_jitsi_room(setup.room_a, setup.bob).allowed

    assert len(calls) == checks_before
    bob_view.refresh_from_db()
    assert bob_view.jitsi_joined_at is not None


def test_room_is_freed_when_everyone_admitted_has_left(room_limit, setup):
    alice_view = enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed

    alice_view.end = now()
    alice_view.save()

    assert admit_to_jitsi_room(setup.room_b, setup.bob).allowed


def test_denied_users_do_not_keep_a_room_running(room_limit, setup):
    alice_view = enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed

    alice_view.end = now()
    alice_view.save()
    enter(setup.room_a, setup.carol)

    # Bob is still in room B, but was never admitted, so A can start again.
    assert admit_to_jitsi_room(setup.room_a, setup.carol).allowed


def test_limit_counts_rooms_across_the_organizers_events(room_limit, setup):
    policy, calls = room_limit
    policy["limit"] = 2
    other_event_room = make_room(make_event(setup.organizer, "other"), "C")
    enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    enter(other_event_room, setup.bob)
    admit_to_jitsi_room(other_event_room, setup.bob)

    enter(setup.room_b, setup.carol)
    assert not admit_to_jitsi_room(setup.room_b, setup.carol).allowed
    assert calls[-1][2] == 3


def test_other_organizers_and_deleted_rooms_are_not_counted(room_limit, setup):
    other_org = Organizer.objects.create(name="Other", slug="other-org")
    foreign_room = make_room(make_event(other_org, "foreign"), "F")
    deleted_room = make_room(setup.event, "Gone")
    for room, user in ((foreign_room, setup.alice), (deleted_room, setup.bob)):
        RoomView.objects.create(room=room, user=user, jitsi_joined_at=now())
    with scopes_disabled():
        Room.objects.filter(pk=deleted_room.pk).update(deleted=True)

    enter(setup.room_a, setup.carol)
    assert admit_to_jitsi_room(setup.room_a, setup.carol).allowed


def test_room_config_rejects_a_call_beyond_the_limit():
    consumer = MagicMock()
    consumer.event.pk = 1
    module = JitsiModule(consumer)
    module.room = SimpleNamespace(id=7, name="A")
    module.module_config = {}
    server = SimpleNamespace(pk=1, url="https://meet.example.org", app_id="", app_secret="")
    denied = EntitlementDecision(allowed=False, message="Room limit reached.")
    room_config = inspect.unwrap(JitsiModule.room_config)

    with patch.object(jitsi_module, "choose_server_for_room", return_value=server), patch.object(
        jitsi_module, "admit_to_jitsi_room", return_value=denied
    ), patch.object(JitsiModule, "can_moderate_room", AsyncMock(return_value=False)):
        with pytest.raises(ConsumerException) as exc_info:
            async_to_sync(room_config)(module, {})

    assert exc_info.value.code == "jitsi.concurrent_rooms_exceeded"
    assert exc_info.value.message == "Room limit reached."
    consumer.send_success.assert_not_called()
