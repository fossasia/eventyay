import pytest
from django.core.exceptions import ValidationError

from eventyay.api.serializers.rooms import RoomSerializer
from eventyay.base.models import BBBServer, Event
from eventyay.base.services.bbb import is_bbb_available
from eventyay.base.services.event import create_room, get_event_config_for_user
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.bbb import BBBModule


@pytest.mark.django_db
def test_is_bbb_available_no_servers():
    BBBServer.objects.all().delete()
    assert is_bbb_available() is False


@pytest.mark.django_db
def test_is_bbb_available_inactive_server():
    BBBServer.objects.all().delete()
    BBBServer.objects.create(url="https://bbb.example.com", secret="sec", active=False)
    assert is_bbb_available() is False


@pytest.mark.django_db
def test_is_bbb_available_active_server():
    BBBServer.objects.all().delete()
    BBBServer.objects.create(url="https://bbb.example.com", secret="sec", active=True)
    assert is_bbb_available() is True


@pytest.mark.django_db
def test_is_bbb_available_disabled_in_event_config():
    BBBServer.objects.all().delete()
    BBBServer.objects.create(url="https://bbb.example.com", secret="sec", active=True)
    event = Event(config={"bbb_disabled": True})
    assert is_bbb_available(event) is False

    event2 = Event(config={"live_features": {"bbb": False}})
    assert is_bbb_available(event2) is False


@pytest.mark.django_db
def test_get_event_config_exposes_bbb_available(admin_user):
    from django.utils.timezone import now

    from eventyay.base.models import Organizer
    organizer = Organizer.objects.create(name="Test Org", slug="test-org")
    event = Event.objects.create(
        organizer=organizer,
        name="Test Event",
        slug="test-event",
        date_from=now(),
        config={},
    )
    BBBServer.objects.all().delete()

    cfg = get_event_config_for_user(event, admin_user)
    assert cfg["world"]["bbb_available"] is False
    assert cfg["world"]["live_features"]["bbb"] is False

    BBBServer.objects.create(url="https://bbb.example.com", secret="sec", active=True)
    cfg2 = get_event_config_for_user(event, admin_user)
    assert cfg2["world"]["bbb_available"] is True
    assert cfg2["world"]["live_features"]["bbb"] is True


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_create_room_blocked_when_bbb_unavailable(admin_user):
    from django.utils.timezone import now

    from eventyay.base.models import Organizer
    organizer = await Organizer.objects.acreate(name="Test Org 2", slug="test-org-2")
    event = await Event.objects.acreate(
        organizer=organizer,
        name="Test Event 2",
        slug="test-event-2",
        date_from=now(),
        config={},
    )
    await BBBServer.objects.all().adelete()

    with pytest.raises(ValidationError) as exc:
        await create_room(
            event,
            {
                "name": "BBB Room",
                "description": "",
                "modules": [{"type": "call.bigbluebutton"}],
            },
            creator=admin_user,
        )
    assert "BBB is currently deactivated by the admin." in str(exc.value)


@pytest.mark.django_db
def test_room_serializer_validation_blocked_when_bbb_unavailable():
    BBBServer.objects.all().delete()
    serializer = RoomSerializer(
        data={
            "name": "New BBB Room",
            "module_config": [{"type": "call.bigbluebutton", "config": {}}],
        }
    )
    assert not serializer.is_valid()
    assert "module_config" in serializer.errors
    assert "BBB is currently deactivated by the admin." in str(serializer.errors["module_config"])


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_bbb_module_call_url_rejected_when_bbb_unavailable():
    class DummyConsumer:
        def __init__(self):
            self.event = Event(config={})
            self.user = None

    module = BBBModule(DummyConsumer())
    await BBBServer.objects.all().adelete()

    with pytest.raises(ConsumerException) as exc:
        await module.call_url({})
    assert exc.value.code == "bbb.unavailable"
    assert "BBB is currently deactivated by the admin." in exc.value.message
