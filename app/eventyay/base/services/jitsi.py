import random
from urllib.parse import urlparse

from django.db import transaction
from django.db.models import Q

from eventyay.base.models import JitsiServer, Room


class JitsiServerUnavailable(Exception):
    pass


def choose_server(event, prefer_server=None):
    servers = JitsiServer.objects.filter(active=True)
    if prefer_server:
        preferred = normalize_server_url(prefer_server)
        if preferred:
            preferred_servers = [
                server
                for server in servers.filter(
                    Q(event_exclusive=event) | Q(event_exclusive__isnull=True)
                )
                if _server_matches_preference(server, preferred)
            ]
            if preferred_servers:
                return random.choice(preferred_servers)
    querysets = (
        servers.filter(event_exclusive=event),
        servers.filter(event_exclusive__isnull=True),
    )
    for qs in querysets:
        available_servers = list(qs)
        if available_servers:
            return random.choice(available_servers)
    return None


@transaction.atomic
def choose_server_for_room(room, prefer_server=None):
    locked_room = Room.objects.select_for_update().select_related("event").get(pk=room.pk)
    jitsi_config = _get_jitsi_config(locked_room)
    selected_server_url = jitsi_config.get("selected_server_url")
    server = choose_server(
        event=locked_room.event,
        prefer_server=prefer_server or selected_server_url,
    )
    if server is None:
        return None

    normalized = normalize_server_url(server.url)
    if normalized and selected_server_url != normalized["url"]:
        jitsi_config["selected_server_url"] = normalized["url"]
        locked_room.save(update_fields=["module_config"])
    return server


def _get_jitsi_config(room):
    for module in room.module_config or []:
        if module.get("type") == "call.jitsi":
            return module.setdefault("config", {})
    return {}


def _server_matches_preference(server, preferred):
    normalized = normalize_server_url(server.url)
    return bool(
        normalized
        and (
            normalized["url"] == preferred["url"]
            or normalized["domain"] == preferred["domain"]
        )
    )


def choose_server_or_raise(event, prefer_server=None):
    server = choose_server(event=event, prefer_server=prefer_server)
    if server is None:
        raise JitsiServerUnavailable(
            f"No active Jitsi server available for event {event.pk}."
        )
    return server


def normalize_server_url(url):
    if not url:
        return None
    url = url.strip()
    if "://" not in url:
        normalized = url.strip("/").lower()
        return {
            "domain": normalized,
            "url": f"https://{normalized}",
            "protocol": "https:",
        }
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    domain = parsed.netloc.lower()
    protocol = parsed.scheme.lower() + ":"
    return {
        "domain": domain,
        "url": f"{parsed.scheme.lower()}://{domain}",
        "protocol": protocol,
    }
