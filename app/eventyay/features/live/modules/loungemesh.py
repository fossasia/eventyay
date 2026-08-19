from channels.db import database_sync_to_async

from eventyay.base.services.loungemesh import issue_join_url
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


class LoungeMeshModule(BaseModule):
    prefix = 'loungemesh'

    @command('room_url')
    @room_action(
        permission_required=Permission.ROOM_LOUNGEMESH_JOIN,
        module_required='call.loungemesh',
    )
    async def room_url(self, body):
        if not self.consumer.user.profile.get('display_name'):
            raise ConsumerException('loungemesh.join.missing_profile')
        moderator = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=Permission.ROOM_LOUNGEMESH_MODERATE,
            room=self.room,
        )
        url = await database_sync_to_async(issue_join_url)(
            self.consumer.event,
            self.room,
            self.consumer.user,
            moderator=moderator,
        )
        if not url:
            raise ConsumerException('loungemesh.failed')
        await self.consumer.send_success({'url': url})
