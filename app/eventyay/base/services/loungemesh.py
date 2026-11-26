import ipaddress
import logging
import socket
import time
import uuid
from urllib.parse import urlparse

import jwt
import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from requests.adapters import HTTPAdapter

from eventyay.base.models import LoungeMeshServer

from .video_server_routing import filter_servers_for_event, is_server_available_for_event


logger = logging.getLogger(__name__)

DEFAULT_FEATURES = {
    "notes": True,
    "whiteboard": True,
    "spatial_chat": True,
}


def normalize_server_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return ""
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


class PinnedIPAdapter(HTTPAdapter):
    """
    HTTPAdapter that pins the underlying socket connection to a pre-validated IP address.
    Preserves TLS SNI, certificate verification, and the HTTP Host header to defend against
    DNS rebinding (TOCTOU SSRF).

    Overrides both get_connection and get_connection_with_tls_context to ensure compatibility
    with requests >= 2.32 (which delegates to get_connection_with_tls_context from send()).
    """

    def __init__(self, pinned_ip: str, *args, **kwargs):
        self.pinned_ip = pinned_ip
        super().__init__(*args, **kwargs)

    def _pin_connection(self, conn):
        old_new_conn = conn._new_conn
        pinned_ip = self.pinned_ip

        def _pinned_new_conn():
            c = old_new_conn()
            orig_host = getattr(c, "host", None)
            c._dns_host = pinned_ip
            if orig_host and not getattr(c, "server_hostname", None):
                c.server_hostname = orig_host
            return c

        conn._new_conn = _pinned_new_conn
        return conn

    def get_connection(self, url, proxies=None):
        conn = super().get_connection(url, proxies=proxies)
        return self._pin_connection(conn)

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        conn = super().get_connection_with_tls_context(request, verify, proxies=proxies, cert=cert)
        return self._pin_connection(conn)


def validate_loungemesh_server_url(
    url: str | None, return_ip: bool = False
) -> tuple[bool, str] | tuple[bool, str, str | None]:
    """Validate a LoungeMesh server URL against SSRF and syntax rules."""

    def _res(ok: bool, msg: str, ip: str | None = None):
        return (ok, msg, ip) if return_ip else (ok, msg)

    if not url or not url.strip():
        return _res(False, _("Server URL is required."))

    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return _res(False, _("Invalid URL: must include a protocol (e.g. https://) and hostname."))
    if not parsed.scheme or not parsed.netloc:
        return _res(False, _("Invalid URL: must include a protocol (e.g. https://) and hostname."))

    if parsed.username or parsed.password:
        return _res(False, _("URL cannot contain embedded credentials."))

    is_debug = getattr(settings, "DEBUG", False)
    allow_private = getattr(
        settings,
        "VIDEO_SERVER_ALLOW_PRIVATE_HOSTS",
        is_debug or getattr(settings, "IS_TESTING", False) or getattr(settings, "TESTING", False),
    )
    hostname = parsed.hostname
    if not hostname:
        return _res(False, _("Invalid hostname."))

    lowered_host = hostname.lower()
    is_local_host = lowered_host in ("localhost", "127.0.0.1", "host.docker.internal", "::1")

    # Scheme check
    if parsed.scheme.lower() not in ("http", "https"):
        return _res(False, _("URL scheme must be http:// or https://."))

    if parsed.scheme.lower() == "http" and not (allow_private or is_local_host):
        return _res(False, _("Production server URLs must use secure https://."))

    # Check for localhost / loopback aliases
    if allow_private and is_local_host:
        return _res(True, "ok", "127.0.0.1" if lowered_host != "::1" else "::1")

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return _res(False, _("Could not resolve hostname '%(host)s'.") % {"host": hostname})

    first_ip = None
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if not first_ip:
            first_ip = ip_str

        if ip_obj.is_link_local or ip_obj.is_unspecified:
            return _res(False, _("Connections to link-local or unspecified IP addresses are not permitted."))

        # In production (allow_private=False and not local host), reject loopback and private IPs
        if not allow_private:
            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_reserved:
                return _res(
                    False,
                    _("Connections to private or local network addresses are not permitted in production."),
                )

    return _res(True, "ok", first_ip or (addr_info[0][4][0] if addr_info else None))


def test_loungemesh_server_connection(url: str, api_secret: str, timeout: float = 5.0) -> tuple[bool, str]:
    """
    Test connectivity and shared secret authentication against a LoungeMesh server.
    Calls GET /api/integration/verify with x-service-secret header.
    Pins connection to validated IP to defend against DNS rebinding (TOCTOU SSRF).
    """
    valid, err, validated_ip = validate_loungemesh_server_url(url, return_ip=True)
    if not valid:
        return False, err

    if not api_secret or not api_secret.strip():
        return False, _("Service secret is required.")

    base_url = normalize_server_url(url)
    verify_url = f"{base_url}/api/integration/verify"
    headers = {
        "x-service-secret": api_secret.strip(),
        "User-Agent": "Eventyay-LoungeMesh-Verifier/1.0",
    }

    session = requests.Session()
    if validated_ip:
        adapter = PinnedIPAdapter(validated_ip)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    try:
        resp = session.get(
            verify_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        logger.warning("LoungeMesh connection timed out for %s", base_url)
        return False, _("Connection timed out while contacting LoungeMesh server.")
    except requests.exceptions.SSLError as e:
        logger.warning("LoungeMesh SSL verification failed for %s: %s", base_url, e)
        return False, _("SSL certificate verification failed. Please verify the server certificate.")
    except requests.exceptions.RequestException as e:
        logger.warning("LoungeMesh connection failed for %s: %s", base_url, e)
        return False, _("Failed to connect to LoungeMesh server. Please verify the URL and network connectivity.")
    finally:
        session.close()

    if resp.status_code == 200:
        try:
            data = resp.json()
            if isinstance(data, dict) and data.get("ok") is True:
                return True, "ok"
        except (ValueError, TypeError):
            pass
        return False, _("Server responded with 200 OK, but returned invalid verification response.")
    elif resp.status_code == 401:
        return False, _("Authentication failed: invalid service secret (EVENTYAY_SERVICE_SECRET mismatch).")
    elif resp.status_code == 404:
        return (
            False,
            _("LoungeMesh verification endpoint not found (404). Ensure the server is running LoungeMesh 0.7.0+."),
        )
    else:
        return False, _("LoungeMesh server returned HTTP status %(code)d.") % {"code": resp.status_code}


def get_loungemesh_server(event=None, prefer_server=None) -> LoungeMeshServer | None:
    servers = LoungeMeshServer.objects.filter(active=True)
    if not servers.exists():
        return None

    if prefer_server:
        preferred = normalize_server_url(prefer_server)
        for s in servers:
            if (
                normalize_server_url(s.url) == preferred or str(s.pk) == str(prefer_server).strip()
            ) and is_server_available_for_event(s, event):
                return s

    search_order = filter_servers_for_event(servers, event)
    for qs in search_order:
        s = qs.first()
        if s:
            return s

    return None


def get_available_loungemesh_servers(event=None) -> list[LoungeMeshServer]:
    """Return all active servers authorized for the event in priority order."""
    servers = LoungeMeshServer.objects.filter(active=True).prefetch_related("events", "organizers")
    if not servers.exists():
        return []

    search_order = filter_servers_for_event(servers, event)
    available: list[LoungeMeshServer] = []
    seen: set[uuid.UUID] = set()
    for qs in search_order:
        for s in qs:
            if s.pk not in seen:
                seen.add(s.pk)
                available.append(s)
    return available


def serialize_loungemesh_server(server: LoungeMeshServer, event=None) -> dict:
    """Serialize a server for client-side display without leaking secrets."""
    scope = "global"
    is_custom = False

    events_cache = (
        server.events.all()
        if hasattr(server, "_prefetched_objects_cache") and "events" in server._prefetched_objects_cache
        else None
    )
    orgs_cache = (
        server.organizers.all()
        if hasattr(server, "_prefetched_objects_cache") and "organizers" in server._prefetched_objects_cache
        else None
    )

    has_event = (
        any(e.pk == event.pk for e in events_cache)
        if (event and events_cache is not None)
        else (event and server.events.filter(pk=event.pk).exists())
    )
    has_any_event = bool(events_cache) if events_cache is not None else server.events.exists()

    org_pk = getattr(getattr(event, "organizer", None), "pk", None)
    has_org = (
        any(o.pk == org_pk for o in orgs_cache)
        if (orgs_cache is not None and org_pk)
        else (org_pk and server.organizers.filter(pk=org_pk).exists())
    )
    has_any_org = bool(orgs_cache) if orgs_cache is not None else server.organizers.exists()

    if event:
        if server.event_exclusive_id == event.id:
            scope = "event"
            is_custom = bool(getattr(server, "is_user_managed", False))
        elif has_event:
            scope = "event"
        elif has_org:
            scope = "organizer"
    elif server.event_exclusive_id or has_any_event:
        scope = "event"
    elif has_any_org:
        scope = "organizer"

    return {
        "id": str(server.pk),
        "url": server.url,
        "scope": scope,
        "is_custom": is_custom,
    }


def loungemesh_is_available(event=None) -> bool:
    if event is not None:
        return get_loungemesh_server(event=event) is not None
    return LoungeMeshServer.objects.filter(active=True).exists()


def issue_signed_grant(
    event,
    room,
    user,
    role: str = "attendee",
    server: LoungeMeshServer | None = None,
    features: dict | None = None,
    expires_in_seconds: int = 300,
) -> str:
    """Issue a signed HS256 grant JWT for LoungeMesh grant exchange.

    Security & Design Notes:
    - Shared Secret: The server's api_secret is intentionally used both as the HS256 signing key
      for grants and as the x-service-secret header during connection verification, pairing with
      EVENTYAY_SERVICE_SECRET in the LoungeMesh deployment.
    - Replay Defense: Grants include short expiry (default 5 minutes), clock-skew padding, and a
      unique cryptographic 'jti' (UUID4). Single-use replay protection is tracked on the LoungeMesh
      receiver side during the /api/integration/access grant exchange.
    - Query String Passing: The grant JWT is delivered via '?grant=' in the iframe URL to allow
      direct, seamless client-side grant exchange on page load.
    """
    if not server or not server.api_secret:
        raise ValueError("LoungeMesh server missing api_secret for grant signing")

    now_ts = int(time.time())
    auth_user = user if user and getattr(user, "is_authenticated", False) else None
    display_name = "Attendee"
    avatar = ""
    if auth_user:
        display_name = getattr(auth_user, "name", "") or getattr(auth_user, "fullname", "")
        if not display_name and hasattr(auth_user, "profile") and isinstance(auth_user.profile, dict):
            display_name = auth_user.profile.get("display_name", "")
        if hasattr(auth_user, "profile") and isinstance(auth_user.profile, dict):
            avatar = auth_user.profile.get("avatar_url", "")
        if not display_name:
            display_name = str(getattr(auth_user, "email", "Attendee")).split("@")[0]

    room_id = getattr(room, "pk", room)
    jitsi_room = f"lms-{event.slug}-{room_id}"
    sub = str(auth_user.pk) if auth_user else f"guest:{uuid.uuid4()}"

    if features is None:
        room_cfg = {}
        for m in (getattr(room, "module_config", None) or []):
            if isinstance(m, dict) and m.get("type") in ("call.loungemesh", "channel.loungemesh"):
                raw_cfg = m.get("config")
                room_cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
                break
        nested_features = room_cfg.get("features") if isinstance(room_cfg.get("features"), dict) else {}
        enable_notes = room_cfg.get("enable_notes")
        if enable_notes is None:
            enable_notes = nested_features.get("notes", True)
        enable_whiteboard = room_cfg.get("enable_whiteboard")
        if enable_whiteboard is None:
            enable_whiteboard = nested_features.get("whiteboard", True)
        enable_spatial_chat = room_cfg.get("enable_spatial_chat")
        if enable_spatial_chat is None:
            enable_spatial_chat = nested_features.get("spatial_chat", True)

        features = {
            "notes": bool(enable_notes),
            "whiteboard": bool(enable_whiteboard),
            "spatial_chat": bool(enable_spatial_chat),
        }
    elif isinstance(features, dict):
        features = {
            "notes": bool(features.get("notes", True)),
            "whiteboard": bool(features.get("whiteboard", True)),
            "spatial_chat": bool(features.get("spatial_chat", True)),
        }

    exp_ts = now_ts + expires_in_seconds
    nbf_ts = now_ts - 10

    is_privileged = role in ("host", "moderator")
    single_user = not is_privileged

    payload = {
        "iss": "eventyay",
        "aud": "loungemesh",
        "jti": str(uuid.uuid4()),
        "sub": sub,
        "name": display_name,
        "avatar": avatar or "",
        "event": event.slug,
        "room": str(room_id),
        "jitsi_room": jitsi_room,
        "role": role,
        "features": features,
        "single_user": single_user,
        "singleUser": single_user,
        "allowed": True,
        "iat": now_ts,
        "nbf": nbf_ts,
        "exp": exp_ts,
    }
    return jwt.encode(payload, server.api_secret, algorithm="HS256")


def issue_join_url(
    event,
    room,
    user,
    moderator: bool = False,
    server: LoungeMeshServer | None = None,
    role: str | None = None,
    features: dict | None = None,
) -> str | None:
    """Generate LoungeMesh join URL carrying a signed grant."""
    server_obj = server or get_loungemesh_server(event)
    if not server_obj or not server_obj.api_secret:
        return None

    # Room must have loungemesh in module_config
    has_loungemesh = any(
        isinstance(m, dict) and m.get("type") in ("call.loungemesh", "channel.loungemesh")
        for m in (room.module_config or [])
    )
    if not has_loungemesh:
        return None

    assigned_role = role or ("moderator" if moderator else "attendee")

    grant = issue_signed_grant(
        event,
        room,
        user,
        role=assigned_role,
        server=server_obj,
        features=features,
    )
    base_url = server_obj.url.rstrip("/")
    jitsi_room = f"lms-{event.slug}-{room.pk}"
    return f"{base_url}/join/{jitsi_room}?grant={grant}"


def loungemesh_embed_origins(event=None) -> list[str]:
    """
    Return allowed embed origins for LoungeMesh iframes.
    When an event is provided, scopes the origins strictly to servers accessible to that event
    (preventing cross-tenant leakage of custom server origins and unconstrained queries).
    """
    origins = set()
    if event:
        servers = get_available_loungemesh_servers(event)
    else:
        servers = LoungeMeshServer.objects.filter(active=True, event_exclusive__isnull=True)
    for s in servers:
        origin = normalize_server_url(s.url)
        if origin:
            origins.add(origin)
    # Default fallbacks
    if getattr(settings, "DEBUG", False):
        origins.add("http://localhost:8780")
    return sorted(list(origins))


def loungemesh_permissions_policy(event=None, extra_origins=None) -> str:
    if isinstance(event, (list, tuple, set)):
        extra_origins = event
        event = None
    origins = set(loungemesh_embed_origins(event=event))
    if extra_origins:
        origins.update(extra_origins)
    formatted_origins = " ".join(f'"{o}"' for o in sorted(origins))
    return (
        f"camera=(self {formatted_origins}), "
        f"microphone=(self {formatted_origins}), "
        f"display-capture=(self {formatted_origins}), "
        f"clipboard-read=(self {formatted_origins}), "
        f"clipboard-write=(self {formatted_origins})"
    )


def apply_loungemesh_embed_headers(response, event=None, extra_origins=None):
    if isinstance(event, (list, tuple, set)):
        extra_origins = event
        event = None
    response["Permissions-Policy"] = loungemesh_permissions_policy(event=event, extra_origins=extra_origins)
    origins = list(loungemesh_embed_origins(event=event))
    if extra_origins:
        origins.extend(extra_origins)
    if not hasattr(response, "_csp_update"):
        response._csp_update = {}
    response._csp_update.setdefault("frame-src", []).extend(origins)
