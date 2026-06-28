import random
from urllib.parse import urlparse

from django.db.models import Q

from eventyay.base.models import JitsiServer


class JitsiServerUnavailable(Exception):
    pass


def choose_server(event, prefer_server=None):
    servers = JitsiServer.objects.filter(active=True)
    querysets = []
    if prefer_server:
        preferred = normalize_server_url(prefer_server)
        preferred_url = preferred["url"] if preferred else prefer_server
        querysets.append(
            servers.filter(url=preferred_url).filter(
                Q(event_exclusive=event) | Q(event_exclusive__isnull=True)
            )
        )
    querysets.extend((
        servers.filter(event_exclusive=event),
        servers.filter(event_exclusive__isnull=True),
    ))
    for qs in querysets:
        available_servers = list(qs)
        if available_servers:
            return random.choice(available_servers)
    return None


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
        normalized = url.strip("/")
        return {
            "domain": normalized,
            "url": f"https://{normalized}",
            "protocol": "https:",
        }
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    protocol = parsed.scheme.lower() + ":"
    return {
        "domain": parsed.netloc,
        "url": f"{parsed.scheme.lower()}://{parsed.netloc}",
        "protocol": protocol,
    }
