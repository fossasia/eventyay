import copy

from django.db import transaction

from eventyay.base.models import (
    Channel,
    Exhibitor,
    ExhibitorLink,
    ExhibitorSocialMediaLink,
)
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
        room, created = Room.objects.get_or_create(
            import_id=room_config.pop("id"),
            event=event,
            defaults={
                "name": room_config["name"],
                "deleted": False,
                "force_join": False,
                "hidden": False,
                "sidebar_hidden": True,
                "setup_complete": False,
            },
        )
        room.name = room_config.pop("name")
        room.description = room_config.pop("description")
        room_config.pop("picture")  # TODO import picure from path or http
        room.trait_grants = room_config.pop("trait_grants", {})
        room.module_config = room_config.pop("modules")
        room.pretalx_id = room_config.pop("pretalx_id", 0)
        room.sorting_priority = i
        # Set ALL boolean fields with proper defaults (all have NOT NULL constraints)
        has_modules = bool(room.module_config)
        # Handle None values explicitly - pop() returns None if key exists with None value
        deleted_val = room_config.pop("deleted", False)
        room.deleted = False if deleted_val is None else deleted_val
        force_join_val = room_config.pop("force_join", False)
        room.force_join = False if force_join_val is None else force_join_val
        setup_complete_val = room_config.pop("setup_complete", has_modules)
        room.setup_complete = has_modules if setup_complete_val is None else setup_complete_val
        hidden_val = room_config.pop("hidden", False)
        room.hidden = False if hidden_val is None else hidden_val
        sidebar_hidden_val = room_config.pop("sidebar_hidden", None)
        if sidebar_hidden_val is None:
            room.sidebar_hidden = not room.setup_complete
        else:
            room.sidebar_hidden = sidebar_hidden_val
        room.save()
        assert not room_config, f"Unused config data: {room_config}"

        for module in room.module_config:
            if module["type"] == "chat.native":
                Channel.objects.get_or_create(room=room, event=event)

    for i, exhibitor_config in enumerate(data.pop("exhibitors")):
        exhibitor, _ = Exhibitor.objects.get_or_create(
            event=event,
            room=Room.objects.get(import_id=exhibitor_config.pop("room")),
            name=exhibitor_config.pop("name"),
        )
        exhibitor.tagline = exhibitor_config.pop("tagline")
        exhibitor.short_text = exhibitor_config.pop("short_text")
        exhibitor.logo = exhibitor_config.pop("logo")
        exhibitor.text_legacy = exhibitor_config.pop("text")
        exhibitor.text_content = exhibitor_config.pop("text_content", [])
        exhibitor.size = exhibitor_config.pop("size")
        exhibitor.sorting_priority = i
        exhibitor.save()
        if "links" in exhibitor_config:
            for link in exhibitor_config.pop("links"):
                el, _ = ExhibitorLink.objects.get_or_create(
                    exhibitor=exhibitor,
                    display_text=link.pop("display_text"),
                    url=link.pop("url"),
                )
                el.save()
        if "social_media_links" in exhibitor_config:
            for social_media_link in exhibitor_config.pop("social_media_links"):
                esml, _ = ExhibitorSocialMediaLink.objects.get_or_create(
                    exhibitor=exhibitor,
                    display_text=social_media_link.pop("display_text"),
                    url=social_media_link.pop("url"),
                )
                esml.save()
        assert not exhibitor_config, f"Unused config data: {room_config}"

    assert not data, f"Unused config data: {data}"
