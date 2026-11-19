import logging

from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from django_scopes import scope

from eventyay.base.models import LoungeMeshServer
from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.base.services.loungemesh import (
    get_available_loungemesh_servers,
    get_loungemesh_server,
    is_event_accessible_for_role,
    issue_join_url,
    normalize_server_url,
    resolve_loungemesh_role,
    serialize_loungemesh_server,
    test_loungemesh_server_connection,
)
from eventyay.base.services.video_server_routing import is_server_available_for_event
from eventyay.core.permissions import Permission
from eventyay.features.live.decorators import command, room_action
from eventyay.features.live.exceptions import ConsumerException
from eventyay.features.live.modules.base import BaseModule


logger = logging.getLogger(__name__)


class LoungeMeshModule(BaseModule):
    prefix = "loungemesh"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_join_url_sync(self, role):
        with scope(event=self.consumer.event):
            room = getattr(self, "room", None)
            if not room:
                return None
            prefer_server = (self.module_config or {}).get("prefer_server")
            server = get_loungemesh_server(self.consumer.event, prefer_server=prefer_server)
            if not server:
                return None
            return issue_join_url(
                self.consumer.event,
                room,
                self.consumer.user,
                role=role,
                server=server,
            )

    async def _get_join_url(self, role):
        return await database_sync_to_async(self._get_join_url_sync)(role)

    @command("room_url")
    @room_action(
        permission_required=[
            Permission.ROOM_LOUNGEMESH_JOIN,
            Permission.ROOM_UPDATE,
            Permission.EVENT_UPDATE,
        ],
        module_required=("call.loungemesh", "channel.loungemesh"),
    )
    async def room_url(self, body):
        is_organizer_area = bool(
            getattr(self.consumer, "is_organizer", False)
            or (getattr(self.consumer.user, "token_id", None) or "").endswith(":orga")
        )
        role = await database_sync_to_async(resolve_loungemesh_role)(
            self.consumer.event,
            self.consumer.user,
            is_organizer_area=is_organizer_area,
        )
        is_host_user = await database_sync_to_async(
            lambda: resolve_loungemesh_role(self.consumer.event, self.consumer.user, is_organizer_area=True) == "host"
        )()
        accessible, reason = await database_sync_to_async(is_event_accessible_for_role)(
            self.consumer.event,
            "host" if is_host_user else role,
        )
        if not accessible:
            log_event(
                'video',
                'connection.room_url',
                OUTCOME_FAILURE,
                error_code=f'event_{reason}',
                event_id=getattr(self.consumer.event, 'pk', None),
                backend='loungemesh',
            )
            if reason == "not_started":
                raise ConsumerException(
                    "loungemesh.event_not_started",
                    "This event has not started yet. Attendees may only join during scheduled event hours.",
                )
            else:
                raise ConsumerException(
                    "loungemesh.event_ended",
                    "This event has ended.",
                )

        url = await self._get_join_url(role)
        if not url:
            log_event(
                'video',
                'connection.room_url',
                OUTCOME_FAILURE,
                error_code='server_unavailable',
                event_id=getattr(self.consumer.event, 'pk', None),
                backend='loungemesh',
            )
            raise ConsumerException("loungemesh.unavailable", "No LoungeMesh server available.")
        log_event(
            'video',
            'connection.room_url',
            OUTCOME_SUCCESS,
            event_id=getattr(self.consumer.event, 'pk', None),
            backend='loungemesh',
        )
        is_moderator = role in ("host", "moderator")
        await self.consumer.send_success({
            "url": url,
            "role": role,
            "moderator": is_moderator,
        })

    @command("servers")
    async def servers(self, body):
        has_perm = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=[Permission.ROOM_UPDATE, Permission.EVENT_UPDATE],
        )
        if not has_perm:
            raise ConsumerException("protocol.denied", "Permission denied.")

        servers_list = await database_sync_to_async(self._get_servers)()
        await self.consumer.send_success({"servers": servers_list})

    def _get_servers(self):
        with scope(event=self.consumer.event):
            servers = get_available_loungemesh_servers(self.consumer.event)
            return [serialize_loungemesh_server(s, self.consumer.event) for s in servers]

    @command("test_server")
    async def test_server(self, body):
        has_perm = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=[Permission.EVENT_UPDATE, Permission.ROOM_UPDATE],
        )
        if not has_perm:
            raise ConsumerException("protocol.denied", "Permission denied.")

        url = str((body or {}).get("url") or "").strip()
        api_secret = str((body or {}).get("api_secret") or "").strip()
        server_id = (body or {}).get("server_id")

        if (not api_secret or api_secret == "*****") and server_id:
            stored_server = await database_sync_to_async(self._get_stored_server)(server_id)
            if not stored_server:
                raise ConsumerException("loungemesh.not_found", "Server not found.")
            if url:
                try:
                    if normalize_server_url(url) != normalize_server_url(stored_server.url):
                        raise ConsumerException(
                            "loungemesh.invalid_url",
                            "Target URL does not match stored server URL.",
                        )
                except ValueError:
                    raise ConsumerException("loungemesh.invalid_url", "Invalid server URL.")
            else:
                url = stored_server.url
            api_secret = stored_server.api_secret

        ok, msg = await database_sync_to_async(test_loungemesh_server_connection)(url, api_secret)
        await self.consumer.send_success({"ok": ok, "message": str(msg)})

    def _get_stored_server(self, server_id):
        with scope(event=self.consumer.event):
            try:
                server = LoungeMeshServer.objects.get(pk=server_id)
                if is_server_available_for_event(server, self.consumer.event):
                    return server
            except (LoungeMeshServer.DoesNotExist, ValueError, ValidationError):
                pass
            return None

    @command("add_server")
    async def add_server(self, body):
        has_perm = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=[Permission.EVENT_UPDATE, Permission.ROOM_UPDATE],
        )
        if not has_perm:
            raise ConsumerException("protocol.denied", "Permission denied.")

        url = str((body or {}).get("url") or "").strip()
        api_secret = str((body or {}).get("api_secret") or "").strip()

        ok, msg = await database_sync_to_async(test_loungemesh_server_connection)(url, api_secret)
        if not ok:
            raise ConsumerException("loungemesh.connection_failed", str(msg))

        server_data = await database_sync_to_async(self._create_custom_server)(url, api_secret)
        await self.consumer.send_success(server_data)

    def _create_custom_server(self, url, api_secret):
        with scope(event=self.consumer.event):
            clean_url = normalize_server_url(url)
            server = LoungeMeshServer.objects.create(
                url=clean_url,
                api_secret=api_secret.strip(),
                active=True,
                event_exclusive=self.consumer.event,
            )
            server.events.add(self.consumer.event)
            return serialize_loungemesh_server(server, self.consumer.event)

    @command("delete_server")
    async def delete_server(self, body):
        has_perm = await self.consumer.event.has_permission_async(
            user=self.consumer.user,
            permission=[Permission.EVENT_UPDATE, Permission.ROOM_UPDATE],
        )
        if not has_perm:
            raise ConsumerException("protocol.denied", "Permission denied.")

        server_id = (body or {}).get("server_id")
        if not server_id:
            raise ConsumerException("protocol.invalid", "server_id is required.")

        deleted = await database_sync_to_async(self._delete_custom_server)(server_id)
        if not deleted:
            raise ConsumerException("loungemesh.cannot_delete", "Only event-exclusive custom servers can be removed.")

        await self.consumer.send_success({"ok": True, "id": str(server_id)})

    def _delete_custom_server(self, server_id):
        with scope(event=self.consumer.event):
            try:
                server = LoungeMeshServer.objects.get(pk=server_id)
                if server.event_exclusive_id == self.consumer.event.id:
                    server.delete()
                    return True
            except (LoungeMeshServer.DoesNotExist, ValueError, ValidationError):
                pass
            return False
