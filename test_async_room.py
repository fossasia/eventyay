import asyncio
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventyay.config.settings')
django.setup()

from asgiref.sync import sync_to_async
from eventyay.base.models import Event, Room, User
from eventyay.base.services.event import get_room_config_for_user

async def main():
    user = await User.objects.afirst()
    event = await Event.objects.afirst()
    if not event:
        print("No event found.")
        return
    room = await Room.objects.filter(event=event).afirst()
    if not room:
        room = await Room.objects.acreate(event=event, name="Test Room")
    
    config = await get_room_config_for_user(str(room.id), str(event.id), user)
    print("Success:", config)

asyncio.run(main())
