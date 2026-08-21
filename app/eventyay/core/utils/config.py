import copy

from django.db import transaction

from eventyay.base.models import Channel
from eventyay.base.models.event import Event
from eventyay.base.models.room import Room


@transaction.atomic
def import_config(data):
    data = copy.deepcopy(data)
    event_config = data.pop("event")
    event, _ = Event.objects.get_or_create(id=event_config.pop("id"))
    event.title = event_config.pop("title")
    event.config = event_config
    event.trait_grants = data.pop("trait_grants", {})
    event.roles = data.pop("roles", {})
    event.save()

    for i, room_config in enumerate(data.pop("rooms")):
        room, _ = Room.objects.get_or_create(
            import_id=room_config.pop("id"),
            event=event,
            defaults={"name": room_config["name"]},
        )
        room.name = room_config.pop("name")
        room.description = room_config.pop("description")
        room_config.pop("picture")  # TODO import picure from path or http
        room.trait_grants = room_config.pop("trait_grants", {})
        room.module_config = room_config.pop("modules")
        room.pretalx_id = room_config.pop("pretalx_id", 0)
        room.sorting_priority = i
        room.save()
        assert not room_config, f"Unused config data: {room_config}"

        for module in room.module_config:
            if module["type"] == "chat.native":
                Channel.objects.get_or_create(room=room, event=event)

    # Older world dumps may include extra keys; they are not imported.
