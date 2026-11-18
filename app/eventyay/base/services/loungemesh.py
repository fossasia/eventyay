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


def validate_loungemesh_server_url(url: str | None) -> tuple[bool, str]:
    """Validate a LoungeMesh server URL against SSRF and syntax rules."""
    if not url or not url.strip():
        return False, _("Server URL is required.")

    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return False, _("Invalid URL: must include a protocol (e.g. https://) and hostname.")
    if not parsed.scheme or not parsed.netloc:
        return False, _("Invalid URL: must include a protocol (e.g. https://) and hostname.")

    if parsed.username or parsed.password:
        return False, _("URL cannot contain embedded credentials.")

    is_debug = getattr(settings, "DEBUG", False)
    is_testing = getattr(settings, "TESTING", False) or "test" in getattr(settings, "SETTINGS_MODULE", "")
    hostname = parsed.hostname
    if not hostname:
        return False, _("Invalid hostname.")

    lowered_host = hostname.lower()
    is_local_host = lowered_host in ("localhost", "127.0.0.1", "host.docker.internal", "::1")

    # Scheme check
    if parsed.scheme.lower() not in ("http", "https"):
        return False, _("URL scheme must be http:// or https://.")

    if parsed.scheme.lower() == "http" and not (is_debug or is_testing or is_local_host):
        return False, _("Production server URLs must use secure https://.")

    # Check for localhost / loopback aliases
    if (is_debug or is_testing) and is_local_host:
        return True, "ok"

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, _("Could not resolve hostname '%(host)s'.") % {"host": hostname}

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip_obj.is_link_local or ip_obj.is_unspecified:
            return False, _("Connections to link-local or unspecified IP addresses are not permitted.")

        # In production (DEBUG=False and not testing and not local host), reject loopback and private IPs
        if not (is_debug or is_testing):
            if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_reserved:
                return False, _("Connections to private or local network addresses are not permitted in production.")

    return True, "ok"


def test_loungemesh_server_connection(url: str, api_secret: str, timeout: float = 5.0) -> tuple[bool, str]:
    """
    Test connectivity and shared secret authentication against a LoungeMesh server.
    Calls GET /api/integration/verify with x-service-secret header.
    """
    valid, err = validate_loungemesh_server_url(url)
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

    try:
        resp = requests.get(
            verify_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return False, _("Connection timed out while contacting LoungeMesh server.")
    except requests.exceptions.SSLError as e:
        return False, _("SSL certificate verification failed: %(err)s") % {"err": str(e)}
    except requests.exceptions.RequestException as e:
        return False, _("Failed to connect to LoungeMesh server: %(err)s") % {"err": str(e)}

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
        if events_cache is not None
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
            is_custom = True
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


def _resolve_platform_principal(user):
    """
    Resolve the platform User account for team permission evaluation.
    Event-scoped Video users have event_id set and do not hold direct team memberships;
    their permissions are attached to the platform user account (event__isnull=True).
    """
    if not user:
        return None
    if getattr(user, "event_id", None) is None and hasattr(user, "has_event_permission"):
        return user

    email = getattr(user, "email", None)
    if not email and hasattr(user, "profile") and isinstance(user.profile, dict):
        email = user.profile.get("contact_email")

    if email:
        from django_scopes import scopes_disabled

        from eventyay.base.models import User

        with scopes_disabled():
            platform_user = (
                User.objects.filter(event__isnull=True, email__iexact=str(email).strip())
                .order_by("id")
                .first()
            )
            if platform_user:
                return platform_user

    return user


def resolve_loungemesh_role(event, user, is_organizer_area: bool = False) -> str:
    """
    Resolve LoungeMesh permission level:
    - Anyone watching on public view (is_organizer_area=False) is ALWAYS an attendee.
    - Only in organizer area (is_organizer_area=True):
      - Admin mode active (admin trait in user traits) -> host
      - can_change_event_settings -> host
      - can_video_moderate -> moderator
      - otherwise -> attendee
    """
    if not is_organizer_area:
        return "attendee"

    if not user or not getattr(user, "is_authenticated", False):
        return "attendee"

    traits = getattr(user, "traits", None) or []
    if "admin" in traits:
        return "host"

    principal = _resolve_platform_principal(user)

    slug = getattr(event, "slug", "")
    if slug:
        moderator_trait = f"eventyay-video-event-{slug}-video-moderator"
        if moderator_trait in traits:
            if hasattr(principal, "has_event_permission") and getattr(event, "organizer", None):
                if principal.has_event_permission(event.organizer, event, "can_change_event_settings"):
                    return "host"
            return "moderator"

    if hasattr(principal, "has_event_permission") and event and getattr(event, "organizer", None):
        if principal.has_event_permission(event.organizer, event, "can_change_event_settings"):
            return "host"
        if principal.has_event_permission(event.organizer, event, "can_video_moderate"):
            return "moderator"

    return "attendee"


def issue_signed_grant(
    event,
    room,
    user,
    role: str = "attendee",
    server: LoungeMeshServer | None = None,
    features: dict | None = None,
    expires_in_seconds: int = 7200,
) -> str:
    """Issue a signed HS256 grant JWT for LoungeMesh grant exchange."""
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
                room_cfg = m.get("config", {}) or {}
                break
        features = {
            "notes": room_cfg.get("enable_notes", True),
            "whiteboard": room_cfg.get("enable_whiteboard", True),
            "spatial_chat": room_cfg.get("enable_spatial_chat", True),
        }

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
        "allowed": True,
        "iat": now_ts,
        "nbf": now_ts - 10,
        "exp": now_ts + expires_in_seconds,
    }
    return jwt.encode(payload, server.api_secret, algorithm="HS256")


def issue_join_url(
    event,
    room,
    user,
    role: str | None = None,
    server: LoungeMeshServer | None = None,
    features: dict | None = None,
    is_organizer_area: bool = False,
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

    assigned_role = role or resolve_loungemesh_role(event, user, is_organizer_area=is_organizer_area)
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


def loungemesh_embed_origins() -> list[str]:
    origins = set()
    for s in LoungeMeshServer.objects.filter(active=True):
        origin = normalize_server_url(s.url)
        if origin:
            origins.add(origin)
    # Default fallbacks
    origins.add("http://localhost:8780")
    origins.add("https://loungemesh.com")
    return sorted(list(origins))


def loungemesh_permissions_policy(extra_origins=None) -> str:
    origins = set(loungemesh_embed_origins())
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


def apply_loungemesh_embed_headers(response, extra_origins=None):
    response["Permissions-Policy"] = loungemesh_permissions_policy(extra_origins)
    origins = list(loungemesh_embed_origins())
    if extra_origins:
        origins.extend(extra_origins)
    if not hasattr(response, "_csp_update"):
        response._csp_update = {}
    response._csp_update.setdefault("frame-src", []).extend(origins)
