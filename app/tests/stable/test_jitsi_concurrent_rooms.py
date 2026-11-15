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
from eventyay.base.services import video_entitlements as jitsi_entitlements
from eventyay.base.services.room import start_view
from eventyay.base.services.video_entitlements import (
    JITSI_CONCURRENT_ROOMS_CAPABILITY,
    admit_to_jitsi_room,
    carry_jitsi_admission,
    release_jitsi_room,
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


def test_other_organizers_are_not_counted(room_limit, setup):
    other_org = Organizer.objects.create(name="Other", slug="other-org")
    foreign_room = make_room(make_event(other_org, "foreign"), "F")
    RoomView.objects.create(room=foreign_room, user=setup.alice, jitsi_joined_at=now())

    enter(setup.room_a, setup.carol)
    assert admit_to_jitsi_room(setup.room_a, setup.carol).allowed


def test_deleted_room_counts_while_its_call_continues(room_limit, setup):
    alice_view = enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    with scopes_disabled():
        Room.objects.filter(pk=setup.room_a.pk).update(deleted=True)

    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed

    alice_view.end = now()
    alice_view.save()
    assert admit_to_jitsi_room(setup.room_b, setup.bob).allowed


def test_room_that_stops_using_jitsi_is_not_counted(room_limit, setup):
    enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    with scopes_disabled():
        Room.objects.filter(pk=setup.room_a.pk).update(
            module_config=[{"type": "livestream.youtube", "config": {}}]
        )

    enter(setup.room_b, setup.bob)
    assert admit_to_jitsi_room(setup.room_b, setup.bob).allowed


def test_user_without_an_open_view_is_not_admitted(room_limit, setup):
    policy, calls = room_limit
    decision = admit_to_jitsi_room(setup.room_a, setup.alice)

    assert not decision.allowed
    assert decision.reason_code == "not_in_room"
    assert calls == []
    assert running_jitsi_room_ids(setup.organizer) == set()


def test_leaving_the_call_frees_the_room(room_limit, setup):
    alice_view = enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice)
    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed

    release_jitsi_room(setup.room_a, setup.alice)

    alice_view.refresh_from_db()
    assert alice_view.end is None
    assert alice_view.jitsi_joined_at is None
    assert admit_to_jitsi_room(setup.room_b, setup.bob).allowed


def test_second_browser_keeps_the_call_counted(room_limit, setup):
    start_view.func(setup.room_a, setup.alice)
    assert admit_to_jitsi_room(setup.room_a, setup.alice).allowed

    # Alice opens room A in a second browser; the first view is replaced.
    new_view, _count = start_view.func(setup.room_a, setup.alice)
    assert new_view.jitsi_joined_at is not None

    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed
    # The second browser joins the call that is already running.
    assert admit_to_jitsi_room(setup.room_a, setup.alice).allowed


def test_leaving_in_one_browser_keeps_the_other_counted(room_limit, setup):
    first = enter(setup.room_a, setup.alice)
    second = enter(setup.room_a, setup.alice)
    admit_to_jitsi_room(setup.room_a, setup.alice, first)
    admit_to_jitsi_room(setup.room_a, setup.alice, second)

    release_jitsi_room(setup.room_a, setup.alice, first)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.jitsi_joined_at is None
    assert second.jitsi_joined_at is not None
    enter(setup.room_b, setup.bob)
    assert not admit_to_jitsi_room(setup.room_b, setup.bob).allowed


def test_admission_with_a_view_marks_only_that_view(room_limit, setup):
    first = enter(setup.room_a, setup.alice)
    second = enter(setup.room_a, setup.alice)

    assert admit_to_jitsi_room(setup.room_a, setup.alice, second).allowed

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.jitsi_joined_at is None
    assert second.jitsi_joined_at is not None


def test_admission_carry_rechecks_after_a_concurrent_leave(setup):
    view = enter(setup.room_a, setup.alice)
    RoomView.objects.filter(pk=view.pk).update(jitsi_joined_at=now())
    previous = RoomView.objects.filter(pk=view.pk)
    original_lock = jitsi_entitlements._lock_organizer

    def leave_while_waiting_for_the_lock(organizer_id):
        # The call ends between the unlocked read and the locked re-check.
        RoomView.objects.filter(pk=view.pk).update(jitsi_joined_at=None)
        original_lock(organizer_id)

    with patch.object(jitsi_entitlements, "_lock_organizer", leave_while_waiting_for_the_lock):
        assert carry_jitsi_admission(setup.room_a, setup.alice, previous) is False


def make_jitsi_module():
    consumer = MagicMock()
    consumer.event.pk = 1
    consumer.event.id = 1
    consumer.user = SimpleNamespace(pk=1, profile={}, email="alice@example.com", fullname="Alice")
    consumer.send_success = AsyncMock()
    module = JitsiModule(consumer)
    module.room = Room(pk=7, name="A")
    module.module_config = {}
    return module, consumer


@pytest.mark.parametrize(
    "reason_code,error_code",
    [
        ("tier_limit_exceeded", "jitsi.concurrent_rooms_exceeded"),
        ("not_in_room", "jitsi.not_in_room"),
    ],
)
def test_room_config_rejects_calls_that_are_not_admitted(reason_code, error_code):
    module, consumer = make_jitsi_module()
    server = SimpleNamespace(pk=1, url="https://meet.example.org", app_id="", app_secret="")
    denied = EntitlementDecision(allowed=False, reason_code=reason_code, message="Denied.")
    room_config = inspect.unwrap(JitsiModule.room_config)

    with patch.object(jitsi_module, "choose_server_for_room", return_value=server), patch.object(
        jitsi_module, "admit_to_jitsi_room", return_value=denied
    ), patch.object(JitsiModule, "can_moderate_room", AsyncMock(return_value=False)):
        with pytest.raises(ConsumerException) as exc_info:
            async_to_sync(room_config)(module, {})

    assert exc_info.value.code == error_code
    assert exc_info.value.message == "Denied."
    consumer.send_success.assert_not_called()


def test_room_config_failure_before_admission_takes_no_slot():
    module, consumer = make_jitsi_module()
    server = SimpleNamespace(pk=1, url="https://meet.example.org", app_id="", app_secret="")
    room_config = inspect.unwrap(JitsiModule.room_config)

    with patch.object(jitsi_module, "choose_server_for_room", return_value=server), patch.object(
        jitsi_module, "admit_to_jitsi_room"
    ) as admit, patch.object(JitsiModule, "can_moderate_room", AsyncMock(side_effect=RuntimeError)):
        with pytest.raises(RuntimeError):
            async_to_sync(room_config)(module, {})

    admit.assert_not_called()


def test_leave_command_releases_this_connections_view():
    module, consumer = make_jitsi_module()
    view = object()
    consumer.components = {"room": SimpleNamespace(current_views={module.room: view})}
    leave = inspect.unwrap(JitsiModule.leave)

    with patch.object(jitsi_module, "release_jitsi_room") as release:
        async_to_sync(leave)(module, {})

    release.assert_called_once_with(module.room, consumer.user, view)
    consumer.send_success.assert_called_once_with({})


def test_migration_counts_calls_running_at_deploy(setup):
    from datetime import timedelta
    from importlib import import_module

    from django.apps import apps

    migration = import_module("eventyay.base.migrations.0091_roomview_jitsi_joined_at")
    youtube_room = make_room(setup.event, "Stream")
    with scopes_disabled():
        Room.objects.filter(pk=youtube_room.pk).update(module_config=[{"type": "livestream.youtube"}])
    current = enter(setup.room_a, setup.alice)
    stale = enter(setup.room_b, setup.bob)
    RoomView.objects.filter(pk=stale.pk).update(start=now() - timedelta(hours=7))
    ended = RoomView.objects.create(room=setup.room_a, user=setup.carol, end=now())
    not_jitsi = enter(youtube_room, setup.carol)

    migration.count_running_jitsi_calls(apps, None)

    for view in (current, stale, ended, not_jitsi):
        view.refresh_from_db()
    assert current.jitsi_joined_at == current.start
    assert stale.jitsi_joined_at is None
    assert ended.jitsi_joined_at is None
    assert not_jitsi.jitsi_joined_at is None
