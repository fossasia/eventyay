import logging

from channels.db import database_sync_to_async
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError
from django_scopes import scope, scopes_disabled

from eventyay.base.models import LoungeMeshServer, User
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

    def _resolve_platform_user_and_session_sync(self):
        platform_user = None
        platform_user_id = getattr(self.consumer, "platform_user_id", None)
        if platform_user_id:
            with scopes_disabled():
                platform_user = (
                    User.objects.filter(
                        pk=platform_user_id,
                        event__isnull=True,
                        is_active=True,
                        is_spam=False,
                    )
                    .first()
                )
        else:
            explicit_platform_user = getattr(self.consumer, "platform_user", None)
            if explicit_platform_user is not None:
                platform_user = explicit_platform_user
            elif not getattr(self.consumer, "platform_auth_checked", False):
                scope_data = getattr(self.consumer, "scope", None)
                if isinstance(scope_data, dict):
                    scope_user = scope_data.get("user")
                    if scope_user is not None and getattr(scope_user, "is_authenticated", False):
                        pk = getattr(scope_user, "pk", None)
                        if pk and getattr(scope_user, "event_id", None) is None:
                            with scopes_disabled():
                                platform_user = (
                                    User.objects.filter(
                                        pk=pk,
                                        event__isnull=True,
                                        is_active=True,
                                        is_spam=False,
                                    )
                                    .first()
                                )
                        else:
                            platform_user = scope_user

        session_key = getattr(self.consumer, "session_key", None)
        if not session_key and not getattr(self.consumer, "platform_auth_checked", False):
            scope_data = getattr(self.consumer, "scope", None)
            if isinstance(scope_data, dict):
                session = scope_data.get("session")
                session_key = getattr(session, "session_key", None)

        return platform_user, session_key

    def _resolve_role_and_access_sync(self, is_organizer_area: bool):
        platform_user, session_key = self._resolve_platform_user_and_session_sync()
        role = resolve_loungemesh_role(
            self.consumer.event,
            self.consumer.user,
            is_organizer_area=is_organizer_area,
            platform_user=platform_user,
            session_key=session_key,
        )
        is_host_user = (
            resolve_loungemesh_role(
                self.consumer.event,
                self.consumer.user,
                is_organizer_area=True,
                platform_user=platform_user,
                session_key=session_key,
            )
            == "host"
        )
        accessible, reason = is_event_accessible_for_role(
            self.consumer.event,
            "host" if is_host_user else role,
        )
        return role, accessible, reason

    def _get_join_url_sync(self, role):
        with scope(event=self.consumer.event):
            room = getattr(self, "room", None)
            if not room:
                return None
            try:
                room.refresh_from_db()
            except (ObjectDoesNotExist, DatabaseError):
                pass
            prefer_server = None
            for m in (room.module_config or []):
                if isinstance(m, dict) and m.get("type") in ("call.loungemesh", "channel.loungemesh"):
                    cfg = m.get("config") or {}
                    prefer_server = cfg.get("prefer_server")
                    break
            if not prefer_server:
                prefer_server = (self.module_config or {}).get("prefer_server")
            server = get_loungemesh_server(self.consumer.event, prefer_server=prefer_server)
            if not server:
                return None
            platform_user, session_key = self._resolve_platform_user_and_session_sync()
            return issue_join_url(
                self.consumer.event,
                room,
                self.consumer.user,
                role=role,
                server=server,
                platform_user=platform_user,
                session_key=session_key,
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
        is_organizer_area = bool(getattr(self.consumer, "is_organizer", False))
        role, accessible, reason = await database_sync_to_async(self._resolve_role_and_access_sync)(
            is_organizer_area
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

        user_id = getattr(self.consumer.user, "pk", "anon")
        rate_key = f"lm_test_rate:{self.consumer.event.pk}:{user_id}"
        if cache.get(rate_key, 0) >= 120:
            raise ConsumerException(
                "loungemesh.rate_limited",
                "Too many requests. Please wait a moment before trying again.",
            )
        cache.set(rate_key, cache.get(rate_key, 0) + 1, timeout=60)

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
        clean_url = normalize_server_url(url)
        if not clean_url:
            raise ConsumerException("loungemesh.invalid_url", "Invalid server URL.")

        user_id = getattr(self.consumer.user, "pk", "anon")
        rate_key = f"lm_add_rate:{self.consumer.event.pk}:{user_id}"
        if cache.get(rate_key, 0) >= 60:
            raise ConsumerException(
                "loungemesh.rate_limited",
                "Too many requests. Please wait a moment before trying again.",
            )
        cache.set(rate_key, cache.get(rate_key, 0) + 1, timeout=60)

        check_err = await database_sync_to_async(self._check_server_limit_and_duplicate)(clean_url)
        if check_err:
            raise ConsumerException(check_err[0], check_err[1])

        ok, msg = await database_sync_to_async(test_loungemesh_server_connection)(url, api_secret)
        if not ok:
            raise ConsumerException("loungemesh.connection_failed", str(msg))

        server_data = await database_sync_to_async(self._create_custom_server)(clean_url, api_secret)
        await self.consumer.send_success(server_data)

    def _check_server_limit_and_duplicate(self, clean_url):
        with scope(event=self.consumer.event):
            qs = LoungeMeshServer.objects.filter(event_exclusive=self.consumer.event)
            if qs.count() >= 5:
                return ("loungemesh.limit_reached", "Maximum of 5 custom servers allowed per event.")
            if qs.filter(url=clean_url).exists():
                return ("loungemesh.duplicate_server", "A server with this URL is already configured for this event.")
            return None

    def _create_custom_server(self, clean_url, api_secret):
        with scope(event=self.consumer.event):
            server = LoungeMeshServer.objects.create(
                url=clean_url,
                api_secret=api_secret.strip(),
                active=True,
                is_user_managed=True,
                event_exclusive=self.consumer.event,
            )
            server.events.add(self.consumer.event)
            log_event(
                'video',
                'loungemesh.server.add',
                OUTCOME_SUCCESS,
                event_id=getattr(self.consumer.event, 'pk', None),
                backend='loungemesh',
                server_id=str(server.pk),
                server_url=clean_url,
            )
            try:
                self.consumer.event.log_action(
                    'eventyay.video.loungemesh.server.added',
                    user=getattr(self.consumer, 'user', None),
                    data={'server_id': server.pk, 'url': clean_url},
                )
            except (ObjectDoesNotExist, DatabaseError, AttributeError):
                pass
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
                if server.event_exclusive_id == self.consumer.event.id and server.is_user_managed:
                    server_url = server.url
                    server.delete()
                    log_event(
                        'video',
                        'loungemesh.server.delete',
                        OUTCOME_SUCCESS,
                        event_id=getattr(self.consumer.event, 'pk', None),
                        backend='loungemesh',
                        server_id=str(server_id),
                        server_url=server_url,
                    )
                    try:
                        self.consumer.event.log_action(
                            'eventyay.video.loungemesh.server.deleted',
                            user=getattr(self.consumer, 'user', None),
                            data={'server_id': server_id, 'url': server_url},
                        )
                    except (ObjectDoesNotExist, DatabaseError, AttributeError):
                        pass
                    return True
            except (LoungeMeshServer.DoesNotExist, ValueError, ValidationError):
                pass
            return False
