import asyncio
import hashlib
import logging
import random
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlparse

import aiohttp
import pytz
from channels.db import database_sync_to_async
from django.conf import settings
from django.db import models, transaction
from django.db.models import Count, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.html import escape
from lxml import etree
from yarl import URL

from eventyay.base.models import BBBServer, BBBCall

logger = logging.getLogger(__name__)


def get_url(operation, params, base_url, secret):
    encoded = urlencode(params)
    payload = operation + encoded + secret
    checksum = hashlib.sha1(payload.encode()).hexdigest()
    return urljoin(
        base_url, "api/" + operation + "?" + encoded + "&checksum=" + checksum
    )


def escape_name(name):
    # Some things break BBB apparently…
    return name.replace(":", "")


def choose_server(event, room=None, prefer_server=None):
    servers = BBBServer.objects.filter(active=True)

    # If we're looking for a server to put a direct message on (no room), we'll take a server with
    # the lowest 'cost', which means it is least used *right now*.
    # If we're looking to place a room, this makes less sense since 95% of Eventyay rooms are created
    # *days* before their peak usage times. However, peak usage often coincides for rooms in the same
    # event, so we'll try to distribute them evenly.
    if not room:
        servers = (
            servers.filter(rooms_only=False)
            .annotate(relevant_cost=F("cost"))
            .order_by("relevant_cost")
        )
    else:
        servers = servers.annotate(
            relevant_cost=Coalesce(
                Subquery(
                    BBBCall.objects.filter(room__event=event, server_id=OuterRef("pk"))
                    .values("server_id")
                    .order_by()
                    .annotate(c=Count("server_id"))
                    .values("c"),
                    output_field=models.IntegerField(),
                ),
                0,
            )
        ).order_by("relevant_cost")

    search_order = [
        servers.filter(url=prefer_server).filter(
            Q(event_exclusive=event) | Q(event_exclusive__isnull=True)
        ),
        servers.filter(event_exclusive=event),
        servers.filter(event_exclusive__isnull=True),
    ]
    for qs in search_order:
        servers = list(qs)
        if not servers:
            continue

        # Servers are sorted by cost, let's do a random pick if we have multiple with the smallest cost
        smallest_cost = servers[0].relevant_cost
        server = random.choice([s for s in servers if s.relevant_cost == smallest_cost])

        if len(servers) > 1:
            # Usually, if there are multiple servers, a cron job should be set up to the bbb_update_cost management
            # command that calculates an actual cost function based on the server load (see there for a definition of
            # the cost function). However, if the cron job does not run (or does not run soon enough), this little
            # UPDATE statement will make sure we have a round-robin-like distribution among the servers by increasing
            # the cost value temporarily with every added meeting.
            BBBServer.objects.filter(pk=server.pk).update(cost=F("cost") + Value(10))
        return server


@database_sync_to_async
@transaction.atomic
def get_create_params_for_call_id(call_id, record, user):
    try:
        call = BBBCall.objects.get(id=call_id, invited_members__in=[user])
        if not call.server.active:
            call.server = choose_server(event=call.event)
            call.save(update_fields=["server"])
    except BBBCall.DoesNotExist:
        return None, None

    create_params = {
        "name": "Call",
        "meetingID": call.meeting_id,
        "attendeePW": call.attendee_pw,
        "moderatorPW": call.moderator_pw,
        "record": "true" if record else "false",
        "meta_Source": "eventyay",
        "meta_Call": str(call_id),
        "lockSettingsDisablePrivateChat": "true",
    }
    if call.voice_bridge:
        create_params["voiceBridge"] = call.voice_bridge
    if call.guest_policy:
        create_params["guestPolicy"] = call.guest_policy
    return create_params, call.server


@database_sync_to_async
def get_call_for_room(room):
    return BBBCall.objects.select_related("server").filter(room=room).first()


@database_sync_to_async
@transaction.atomic
def get_create_params_for_room(
    room, record, voice_bridge, guest_policy, prefer_server=None
):
    try:
        call = BBBCall.objects.get(room=room)
        if not call.server.active:
            call.server = choose_server(event=room.event, room=room)
            call.save(update_fields=["server"])
        if call.guest_policy != guest_policy:
            call.guest_policy = guest_policy
            call.save(update_fields=["guest_policy"])
        if call.voice_bridge != voice_bridge:
            call.voice_bridge = voice_bridge
            call.save(update_fields=["voice_bridge"])
    except BBBCall.DoesNotExist:
        call = BBBCall.objects.create(
            room=room,
            event=room.event,
            server=choose_server(
                event=room.event, room=room, prefer_server=prefer_server
            ),
            voice_bridge=voice_bridge,
            guest_policy=guest_policy,
        )

    m = [m for m in room.module_config if m["type"] == "call.bigbluebutton"][0]
    config = m["config"]
    create_params = {
        "name": room.name or "Meeting",
        "meetingID": call.meeting_id,
        "attendeePW": call.attendee_pw,
        "moderatorPW": call.moderator_pw,
        "record": "true" if record else "false",
        "meta_Source": "eventyay",
        "meta_Event": room.event_id,
        "meta_Room": str(room.id),
        "muteOnStart": ("true" if config.get("bbb_mute_on_start", False) else "false"),
        "lockSettingsDisablePrivateChat": (
            "true"
            if room.event.config.get("bbb_disable_privatechat", True)
            else "false"
        ),
        "lockSettingsDisableCam": (
            "true" if config.get("bbb_disable_cam", False) else "false"
        ),
        "lockSettingsDisablePublicChat": (
            "true" if config.get("bbb_disable_chat", False) else "false"
        ),
    }
    if call.voice_bridge:
        create_params["voiceBridge"] = call.voice_bridge
    if call.guest_policy:
        create_params["guestPolicy"] = call.guest_policy
    return create_params, call.server


class BBBService:
    def __init__(self, event):
        self.event = event

    async def _get(self, url, timeout=30):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(URL(url, encoded=True), timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.error(
                            "Could not contact BBB. Return code: %s",
                            resp.status,
                        )
                        return False

                    body = await resp.text()

                try:
                    root = etree.fromstring(body)
                except etree.XMLSyntaxError:
                    logger.warning(
                        "BBB response contained malformed XML",
                        extra={"url": url},
                    )
                    return False

                returncode_nodes = root.xpath("returncode")
                if not returncode_nodes or returncode_nodes[0].text != "SUCCESS":
                    logger.error("Could not contact BBB. Response: %s", body)
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            logger.exception("Could not contact BBB.")
            return False
        except Exception:
            logger.exception("Unexpected error while contacting BBB")
            return False
        return root

    async def _post(self, url, xmldata):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    URL(url, encoded=True),
                    data=xmldata,
                    headers={"Content-Type": "application/xml"},
                ) as resp:
                    if resp.status != 200:
                        logger.error(
                            "Could not contact BBB. Return code: %s",
                            resp.status,
                        )
                        return False

                    body = await resp.text()

                try:
                    root = etree.fromstring(body)
                except etree.XMLSyntaxError:
                    logger.warning(
                        "BBB response contained malformed XML",
                        extra={"url": url},
                    )
                    return False

                returncode_nodes = root.xpath("returncode")
                if not returncode_nodes or returncode_nodes[0].text != "SUCCESS":
                    logger.error("Could not contact BBB. Response: %s", body)
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            logger.exception("Could not contact BBB.")
            return False
        except Exception:
            logger.exception("Unexpected error while contacting BBB")
            return False
        return root

    async def get_join_url_for_room(self, room, user, moderator=False):
        m = [m for m in room.module_config if m["type"] == "call.bigbluebutton"][0]
        config = m["config"]
        create_params, server = await get_create_params_for_room(
            room,
            record=config.get("record", False),
            voice_bridge=config.get("voice_bridge", None),
            prefer_server=config.get("prefer_server", None),
            guest_policy=(
                "ASK_MODERATOR"
                if config.get("waiting_room", False)
                else "ALWAYS_ACCEPT"
            ),
        )
        create_url = get_url("create", create_params, server.url, server.secret)

        presentation = config.get("presentation", None)
        if presentation:
            xml = "<modules>"
            xml += '<module name="presentation"><document url="{}" /></module>'.format(
                escape(presentation)
            )
            xml += "</modules>"
            req = await self._post(create_url, xml)
        else:
            req = await self._get(create_url)

        if req is False:
            return

        if user.profile.get("avatar", {}).get("url"):
            avatar = {"avatarURL": user.profile.get("avatar", {}).get("url")}
        else:
            avatar = {}

        scheme = (
            "http://" if settings.DEBUG else "https://"
        )  # TODO: better determinator?
        domain = self.event.domain or settings.SITE_NETLOC
        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": escape_name(user.profile.get("display_name", "")),
                "userID": str(user.pk),
                "password": (
                    create_params["moderatorPW"]
                    if moderator
                    else create_params["attendeePW"]
                ),
                "joinViaHtml5": "true",
                **avatar,
                "guest": (
                    "true"
                    if not moderator and config.get("waiting_room", False)
                    else "false"
                ),
                "userdata-bbb_custom_style_url": scheme
                + domain
                + reverse("live:css.bbb"),
                "userdata-bbb_show_public_chat_on_login": "false",
                # "userdata-bbb_mirror_own_webcam": "true",  unfortunately mirrors for everyone, which breaks things
                "userdata-bbb_skip_check_audio": "true",
                "userdata-bbb_listen_only_mode": (
                    "false" if config.get("auto_microphone", False) else "true"
                ),
                "userdata-bbb_auto_share_webcam": (
                    "true" if config.get("auto_camera", False) else "false"
                ),
                "userdata-bbb_skip_video_preview": (
                    "true" if config.get("auto_camera", False) else "false"
                ),
                # For some reason, bbb_auto_swap_layout does what you expect from bbb_hide_presentation
                "userdata-bbb_auto_swap_layout": (
                    "true" if config.get("hide_presentation", False) else "false"
                ),
            },
            server.url,
            server.secret,
        )

    async def get_join_url_for_call_id(self, call_id, user):
        create_params, server = await get_create_params_for_call_id(
            call_id, False, user
        )
        if not create_params:
            return
        create_url = get_url("create", create_params, server.url, server.secret)
        if await self._get(create_url) is False:
            return

        if user.profile.get("avatar", {}).get("url"):
            avatar = {"avatarURL": user.profile.get("avatar", {}).get("url")}
        else:
            avatar = {}

        scheme = (
            "http://" if settings.DEBUG else "https://"
        )  # TODO: better determinator?
        domain = self.event.domain or settings.SITE_NETLOC
        return get_url(
            "join",
            {
                "meetingID": create_params["meetingID"],
                "fullName": escape_name(user.profile.get("display_name", "")),
                **avatar,
                "userID": str(user.pk),
                "password": create_params["moderatorPW"],
                "joinViaHtml5": "true",
                "userdata-bbb_custom_style_url": scheme
                + domain
                + reverse("live:css.bbb"),
                "userdata-bbb_show_public_chat_on_login": "false",
                # "userdata-bbb_mirror_own_webcam": "true",  unfortunately mirrors for everyone, which breaks things
                "userdata-bbb_auto_share_webcam": "true",
                "userdata-bbb_skip_check_audio": "true",
                "userdata-bbb_listen_only_mode": "false",  # in a group call, listen-only does not make sense
                "userdata-bbb_auto_swap_layout": "true",  # in a group call, you'd usually not have a presentation
            },
            server.url,
            server.secret,
        )

    @database_sync_to_async
    def _get_possible_servers(self):
        return list(
            BBBServer.objects.filter(
                Q(event_exclusive=self.event) | Q(event_exclusive__isnull=True),
                active=True,
            )
        )

    def _is_recording_published(self, state):
        if not state:
            return False
        return state.lower() == "published"

    async def get_recordings_for_room(self, room):
        def get_node_text(node, path):
            nodes = node.xpath(path)
            if not nodes:
                return None
            return nodes[0].text

        def parse_int(value):
            if value is None:
                return None
            return int(value)

        recordings = []
        call = await get_call_for_room(room)
        if not call:
            return []

        for server in await self._get_possible_servers():
            recordings_url = get_url(
                "getRecordings",
                {"meetingID": call.meeting_id, "state": "any"},
                server.url,
                server.secret,
            )
            root = await self._get(recordings_url, timeout=10)
            if root is False:
                logger.warning(
                    "BBB recordings request failed",
                    extra={
                        "server_url": server.url,
                        "event_id": self.event.id,
                        "room_id": room.id,
                    },
                )
                continue

            tz = pytz.timezone(self.event.timezone)
            for rec in root.xpath("recordings/recording"):
                try:
                    state = get_node_text(rec, "state")
                    if not self._is_recording_published(state):
                        continue

                    start_time = parse_int(get_node_text(rec, "startTime"))
                    end_time = parse_int(get_node_text(rec, "endTime"))
                    participants = parse_int(get_node_text(rec, "participants"))
                    if start_time is None or end_time is None or participants is None:
                        continue

                    url_presentation = None
                    url_screenshare = None
                    url_video = None
                    url_notes = None
                    for f in rec.xpath("playback/format"):
                        format_type = get_node_text(f, "type")
                        format_url = get_node_text(f, "url")
                        if not format_type or not format_url:
                            continue
                        if format_type == "presentation":
                            url_presentation = format_url
                        elif format_type == "screenshare":
                            url_screenshare = format_url
                        elif format_type == "video":
                            url_video = format_url
                        elif format_type == "notes":
                            url_notes = format_url
                        elif format_type == "Video":
                            url_video = format_url
                            # Work around an upstream bug
                            if "///" in url_video:
                                url_video = url_video.replace(
                                    "///",
                                    "//{}/".format(
                                        urlparse(recordings_url).hostname
                                    ),
                                )

                    if (
                        not url_presentation
                        and not url_screenshare
                        and not url_video
                        and not url_notes
                    ):
                        continue

                    recordings.append(
                        {
                            "start": (
                                # BBB outputs timestamps in server time, not UTC :( Let's assume the BBB server time
                                # is the same as ours…
                                datetime.fromtimestamp(
                                    start_time / 1000,
                                    pytz.timezone(settings.TIME_ZONE),
                                )
                            )
                            .astimezone(tz)
                            .isoformat(),
                            "end": (
                                datetime.fromtimestamp(
                                    end_time / 1000,
                                    pytz.timezone(settings.TIME_ZONE),
                                )
                            )
                            .astimezone(tz)
                            .isoformat(),
                            "participants": participants,
                            "state": state.lower() if state else state,
                            "url": url_presentation,
                            "url_video": url_video,
                            "url_screenshare": url_screenshare,
                            "url_notes": url_notes,
                        }
                    )
                except (TypeError, ValueError, IndexError):
                    logger.warning(
                        "BBB recording entry malformed",
                        extra={
                            "server_url": server.url,
                            "event_id": self.event.id,
                            "room_id": room.id,
                        },
                    )
                    continue
        return recordings
