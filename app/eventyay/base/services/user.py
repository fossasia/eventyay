import datetime as dt
import json
import operator
from collections import namedtuple
from datetime import timedelta
from functools import reduce

import jwt
import requests
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Q
from django.db.transaction import atomic
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.eventyay_common.utils import encode_email
from eventyay.features.live.channels import GROUP_USER
from eventyay.base.models import AuditLog
from eventyay.base.models.auth import User
from eventyay.base.models.room import AnonymousInvite
from eventyay.base.models.event import Event, EventView
from eventyay.base.models.orders import Order, OrderPosition
from eventyay.core.permissions import Permission

_WIKI_PROFILE_FIELD_KEYS = (
    "wikimedia_username",
    "wikimania_username",
    "wiki_username",
)


def display_wikimedia_username_from_profile(profile, stored_username):
    if stored_username:
        return stored_username
    fields = (profile or {}).get("fields") or {}
    for key in _WIKI_PROFILE_FIELD_KEYS:
        val = fields.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _is_email_hash_uid_token(token_id):
    if not token_id or len(token_id) != 7:
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in token_id)


def admin_public_fields_from_user_row(user_row, ticket_by_token):
    """Admin-only list fields derived from a User values() row and ticket lookup."""
    tid = user_row["token_id"]
    ticket = (ticket_by_token.get(tid) or {}) if tid else {}
    return {
        "moderation_state": user_row["moderation_state"],
        "token_id": tid,
        "email": (user_row.get("email") or "").strip()
        or ticket.get("contact_email", ""),
        "wikimedia_username": display_wikimedia_username_from_profile(
            user_row["profile"], user_row.get("wikimedia_username")
        ),
        "order_code": ticket.get("order_code"),
        "ticket_code": ticket.get("ticket_code"),
    }


def resolve_wikimedia_usernames_by_email(emails):
    """Return a lowercase email -> Wikimedia username map from account users."""
    uniq = list(dict.fromkeys((e or "").strip().lower() for e in emails if e))
    if not uniq:
        return {}
    rows = (
        User.objects.filter(event__isnull=True, email__in=uniq)
        .exclude(wikimedia_username__isnull=True)
        .exclude(wikimedia_username__exact="")
        .values("email", "wikimedia_username")
    )
    result = {}
    for row in rows:
        email = (row.get("email") or "").strip().lower()
        if email and email not in result:
            result[email] = (row.get("wikimedia_username") or "").strip()
    return result


def admin_public_fields_with_email_fallback(
    user_row, ticket_by_token, email_to_wikimedia
):
    data = admin_public_fields_from_user_row(user_row, ticket_by_token)
    if data.get("wikimedia_username"):
        return data
    email = (data.get("email") or "").strip().lower()
    if email and email in email_to_wikimedia:
        data["wikimedia_username"] = email_to_wikimedia[email]
    return data


def build_admin_ticket_rows_by_token(event_id, token_ids):
    """
    Map a video user's JWT ``uid`` (stored as ``User.token_id``) to Pretix order data.

    Tokens are either ``OrderPosition.pseudonymization_id`` or ``encode_email(order.email)``
    (seven hex characters) as used by presale video join links.
    """
    uniq = list(dict.fromkeys(t for t in token_ids if t))
    if not uniq:
        return {}
    result = {}
    with scopes_disabled():
        for row in OrderPosition.objects.filter(
            order__event_id=event_id,
            pseudonymization_id__in=uniq,
            addon_to__isnull=True,
            canceled=False,
            order__status=Order.STATUS_PAID,
        ).values(
            "pseudonymization_id",
            "secret",
            "order__code",
            "order__email",
        ):
            tid = row["pseudonymization_id"]
            result[tid] = {
                "order_code": row["order__code"],
                "ticket_code": row["secret"],
                "contact_email": (row["order__email"] or "").strip(),
            }
    need_hash = [t for t in uniq if t not in result and _is_email_hash_uid_token(t)]
    if need_hash:
        need_set = {t.upper() for t in need_hash}
        hash_to_email = {}
        with scopes_disabled():
            for email in (
                Order.objects.filter(event_id=event_id)
                .filter(status=Order.STATUS_PAID)
                .exclude(email__isnull=True)
                .exclude(email__exact="")
                .values_list("email", flat=True)
                .iterator(chunk_size=4000)
            ):
                h = encode_email(email).upper()
                if h in need_set and h not in hash_to_email:
                    hash_to_email[h] = email
                if len(hash_to_email) >= len(need_set):
                    break
        emails = list(dict.fromkeys(hash_to_email.values()))
        positions_by_email = {}
        if emails:
            with scopes_disabled():
                rows = (
                    OrderPosition.objects.filter(
                        order__event_id=event_id,
                        order__email__in=emails,
                        order__status=Order.STATUS_PAID,
                        addon_to__isnull=True,
                        canceled=False,
                    )
                    .select_related("order")
                    .order_by("order__email", "-order__datetime", "positionid")
                )
                for pos in rows:
                    key = pos.order.email.lower()
                    if key not in positions_by_email:
                        positions_by_email[key] = {
                            "order_code": pos.order.code,
                            "ticket_code": pos.secret,
                            "contact_email": (pos.order.email or "").strip(),
                        }
        for t in need_hash:
            email = hash_to_email.get(t.upper())
            if not email:
                continue
            row = positions_by_email.get(email.lower())
            if row:
                result[t] = dict(row)
    return result


def get_user_by_id(event_id, user_id):
    try:
        return User.objects.get(id=user_id, event_id=event_id)
    except User.DoesNotExist:
        return


def get_user_by_token_id(event_id, token_id):
    try:
        return User.objects.get(token_id=token_id, event_id=event_id)
    except User.DoesNotExist:
        return


def get_user_by_client_id(event_id, client_id):
    try:
        return User.objects.get(client_id=client_id, event_id=event_id)
    except User.DoesNotExist:
        return


@database_sync_to_async
def get_public_user(event_id, id, include_admin_info=False, trait_badges_map=None):
    user = get_user_by_id(event_id, id)
    if not user:
        return None
    data = user.serialize_public(
        include_admin_info=include_admin_info,
        trait_badges_map=trait_badges_map,
        include_client_state=include_admin_info and user.type == User.UserType.KIOSK,
    )
    if include_admin_info and user.token_id:
        ticket = build_admin_ticket_rows_by_token(event_id, [user.token_id]).get(
            user.token_id
        )
        if ticket:
            data["order_code"] = ticket["order_code"]
            data["ticket_code"] = ticket["ticket_code"]
            if not (data.get("email") or "").strip() and ticket.get("contact_email"):
                data["email"] = ticket["contact_email"]
    if include_admin_info:
        data["wikimedia_username"] = display_wikimedia_username_from_profile(
            user.profile, data.get("wikimedia_username")
        )
    return data


@database_sync_to_async
def get_public_users(
    event_id,
    *,
    ids=None,
    pretalx_ids=None,
    include_admin_info=False,
    trait_badges_map=None,
    include_banned=True,
    require_show_publicly=False,
    type=User.UserType.PERSON,
):
    # This method is called a lot, especially when lots of people join at once (event start, server reboot, …)
    # For performance reasons, we therefore do not initialize model instances and use serialize_public()
    if ids is not None:
        qs = User.objects.filter(id__in=ids, event_id=event_id)
    else:
        qs = User.objects.filter(event_id=event_id, deleted=False).order_by(
            "profile__display_name", "id"
        )
    if require_show_publicly:
        qs = qs.filter(show_publicly=True)
    if pretalx_ids is not None:
        qs = qs.filter(pretalx_id__in=pretalx_ids)
    if type is not None:
        qs = qs.filter(type=type)
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)

    value_fields = (
        "id",
        "type",
        "profile",
        "deleted",
        "moderation_state",
        "token_id",
        "traits",
        "last_login",
        "pretalx_id",
        "client_state",
    )

    if include_admin_info:
        users_data = list(qs.values(*value_fields, "email", "wikimedia_username"))
    else:
        users_data = qs.values(*value_fields).iterator()

    ticket_by_token = {}
    email_to_wikimedia = {}
    if include_admin_info and users_data:
        token_ids = [u["token_id"] for u in users_data if u["token_id"]]
        if token_ids:
            ticket_by_token = build_admin_ticket_rows_by_token(event_id, token_ids)
        admin_rows = [
            admin_public_fields_from_user_row(u, ticket_by_token)
            for u in users_data
        ]
        emails_to_resolve = [
            row["email"]
            for row in admin_rows
            if row.get("email") and not row.get("wikimedia_username")
        ]
        if emails_to_resolve:
            with scopes_disabled():
                email_to_wikimedia = resolve_wikimedia_usernames_by_email(
                    emails_to_resolve
                )

    return [
        dict(
            id=str(u["id"]),
            profile=u["profile"],
            pretalx_id=u["pretalx_id"],
            deleted=u["deleted"],
            inactive=(
                u["last_login"] is None or u["last_login"] < now() - timedelta(hours=36)
            ),
            badges=(
                sorted(
                    list(
                        {
                            badge
                            for trait, badge in trait_badges_map.items()
                            if trait in u["traits"]
                        }
                    )
                )
                if trait_badges_map
                else []
            ),
            **(
                {"client_state": u["client_state"]}
                if include_admin_info and u["type"] == User.UserType.KIOSK
                else {}
            ),
            **(
                admin_public_fields_with_email_fallback(
                    u,
                    ticket_by_token,
                    email_to_wikimedia,
                )
                if include_admin_info
                else {}
            ),
        )
        for u in users_data
    ]


def get_user(
    event=None,
    *,
    with_id=None,
    with_token=None,
    with_client_id=None,
    with_invite_token=None,
):
    if with_id:
        user = get_user_by_id(event.id, with_id)
        return user

    token_id = None
    anonymous_invite = None
    if with_token:
        token_id = with_token["uid"]
        user = get_user_by_token_id(event.id, token_id)
    elif with_client_id:
        user = get_user_by_client_id(event.id, with_client_id)
        if not user and with_invite_token:
            try:
                anonymous_invite = AnonymousInvite.objects.get(
                    short_token=with_invite_token,
                    event=event,
                    expires__gte=now(),
                )
            except AnonymousInvite.DoesNotExist:
                return None
    else:
        raise Exception(
            "get_user was called without valid with_token, with_id or with_client_id"
        )

    if user:
        if with_token and (user.traits != with_token.get("traits")):
            traits = with_token["traits"]
            update_user(event.id, id=user.id, traits=traits)
            user = get_user_by_id(event.id, user.id)
        return user

    traits = with_token.get("traits") if with_token else None
    if not anonymous_invite and not event.has_permission_implicit(
        traits=traits or [],
        permissions=[Permission.EVENT_VIEW],
    ):
        # There is no chance this user gets in, we want to do an early out to prevent empty
        # user profiles from being created
        return

    if token_id:
        user = create_user(
            event_id=event.id,
            token_id=token_id,
            profile=with_token.get("profile") if with_token else None,
            traits=traits,
            pretalx_id=with_token.get("pretalx_id") if with_token else None,
        )
    else:
        user = create_user(
            event_id=event.id,
            client_id=with_client_id,
            anonymous_invite=anonymous_invite,
            traits=traits,
        )
    return user


def create_user(
    event_id,
    *,
    token_id=None,
    client_id=None,
    traits=None,
    profile=None,
    pretalx_id=None,
    anonymous_invite=None,
):
    kwargs = {}
    if anonymous_invite:
        kwargs.update(
            {
                "type": User.UserType.ANONYMOUS,
                "show_publicly": False,
            }
        )
    user = User.objects.create(
        event_id=event_id,
        token_id=token_id,
        client_id=client_id,
        pretalx_id=pretalx_id,
        traits=traits or [],
        profile=profile or {},
        **kwargs,
    )
    if anonymous_invite:
        user.event_grants.create(event_id=event_id, role="__anonymous_event")
        user.room_grants.create(
            event_id=event_id,
            room_id=anonymous_invite.room_id,
            role="__anonymous_room",
        )
    return user


@atomic
def update_user(
    event_id, id, *, traits=None, data=None, is_admin=False, serialize=True
):
    # TODO: Exception handling
    user = (
        User.objects.select_related("event")
        .select_for_update()
        .get(id=id, event_id=event_id)
    )

    if traits is not None:
        if user.traits != traits:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.traits.changed",
                data={
                    "object": str(user.pk),
                    "old": user.traits,
                    "new": traits,
                },
            )
            user.traits = traits
        user.save(update_fields=["traits"])

    if data is not None:
        save_fields = []
        if "profile" in data and data["profile"] != user.profile:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.profile.changed",
                data={
                    "object": str(user.pk),
                    "old": user.profile,
                    "new": data["profile"],
                    "is_admin": is_admin,
                },
            )

            # TODO: Anything we want to validate here?
            user.profile = data.get("profile")
            save_fields.append("profile")

        if is_admin and "pretalx_id" in data and data["pretalx_id"] != user.pretalx_id:
            AuditLog.objects.create(
                event_id=event_id,
                user=user,
                type="auth.user.pretalx_id.changed",
                data={
                    "object": str(user.pk),
                    "old": user.pretalx_id,
                    "new": data["pretalx_id"],
                },
            )
            user.pretalx_id = data.get("pretalx_id")
            save_fields.append("pretalx_id")

        if (
            not is_admin
            and "client_state" in data
            and data["client_state"] != user.client_state
        ) or (
            is_admin
            and user.type == User.UserType.KIOSK
            and "client_state" in data
            and data["client_state"] != user.client_state
        ):
            user.client_state = data.get("client_state")
            save_fields.append("client_state")
            # Legacy eventyay-talk favourite syncing was removed.

        if save_fields:
            user.save(update_fields=save_fields)

    return (
        user.serialize_public(
            trait_badges_map=user.event.config.get("trait_badges_map")
        )
        if serialize
        else user
    )



def start_view(user: User, delete=False):
    # The majority of EventView that go "abandoned" (i.e. ``end`` is never set) are likely caused by server
    # crashes or restarts, in which case ``end`` can't be set. However, after a server crash, the client
    # either reconnects automatically or the user will attempt a reconnect themselves through a page reload,
    # so the most likely end of the previous session is "just before this", and the best assumption is to set
    # the end to "now".
    #
    # Obviously, this is wrong whenever a user has multiple sessions open, e.g. if the same user has the room
    # open in browser A and then opens the same room in browser B, this will set the ``end`` for the session
    # in browser A, even though it's already running. It doesn't matter, though! First, for all our statistics
    # we only count unique users and the result "this user was present at the time" is still correct. Second,
    # the way ``end_view`` is implemented, the session from browser A will still be corrected with the accurate
    # time as soon as browser A leaves.
    previous = EventView.objects.filter(
        user=user, event_id=user.event_id, end__isnull=True
    )
    if delete:
        previous.delete()
    else:
        previous.update(end=now())
    r = EventView.objects.create(event_id=user.event_id, user=user)
    return r


def end_view(view: EventView, delete=False):
    if delete:
        if view.pk:
            view.delete()
    else:
        view.end = now()
        view.save()


LoginResult = namedtuple(
    "LoginResult",
    "user event_config chat_channels chat_notification_counts exhibition_data view",
)


class AuthError(Exception):
    def __init__(self, code):
        self.code = code


def login(
    *,
    event=None,
    token=None,
    client_id=None,
    invite_token=None,
) -> LoginResult:
    from .chat import ChatService
    from .exhibition import ExhibitionService
    from .event import get_event_config_for_user

    user = get_user(
        event=event,
        with_client_id=client_id,
        with_token=token,
        with_invite_token=invite_token,
    )

    if user and user.is_banned:
        raise AuthError("auth.denied")

    if not user or not event.has_permission(
        user=user, permission=Permission.EVENT_VIEW
    ):
        if token:
            raise AuthError("auth.denied")
        else:
            raise AuthError("auth.missing_token")

    user.last_login = now()
    user.save(update_fields=["last_login"])

    # Safely handle missing event.config (can be None for newly created events or misconfigured instances)
    event_config_obj = getattr(event, "config", None) or {}
    track_event_views = bool(event_config_obj.get("track_event_views", False))
    if track_event_views:
        view = start_view(user)
    else:
        view = None

    return LoginResult(
        user=user,
        event_config=get_event_config_for_user(event, user),
        chat_channels=ChatService(event).get_channels_for_user(
            user.pk, is_volatile=False
        ),
        chat_notification_counts=ChatService(event).get_notification_counts(user.pk),
        exhibition_data=ExhibitionService(event).get_exhibition_data_for_user(user.pk),
        view=view,
    )


@database_sync_to_async
@atomic
def get_blocked_users(user, event) -> bool:
    return [
        u.serialize_public(trait_badges_map=event.config.get("trait_badges_map"))
        for u in user.blocked_users.all()
    ]


@database_sync_to_async
@atomic
def set_user_banned(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.BANNED
    user.save(update_fields=["moderation_state"])

    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.banned",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def delete_user(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.soft_delete()

    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.deleted",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_silenced(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    if user.moderation_state == User.ModerationState.BANNED:
        return True
    user.moderation_state = User.ModerationState.SILENCED
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.silenced",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def set_user_free(event, user_id, by_user) -> bool:
    user = get_user_by_id(event_id=event.pk, user_id=user_id)
    if not user:
        return False
    user.moderation_state = User.ModerationState.NONE
    user.save(update_fields=["moderation_state"])
    AuditLog.objects.create(
        event=event,
        user=by_user,
        type="auth.user.reactivated",
        data={
            "object": user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def block_user(event, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(event_id=event.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.add(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        event=event,
        user=blocking_user,
        type="auth.user.blocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
@atomic
def unblock_user(event, blocking_user: User, blocked_user_id) -> bool:
    blocked_user = get_user_by_id(event_id=event.pk, user_id=blocked_user_id)
    if not blocked_user:
        return False

    blocking_user.blocked_users.remove(blocked_user)
    blocked_user.touch()
    AuditLog.objects.create(
        event=event,
        user=blocking_user,
        type="auth.user.unblocked",
        data={
            "object": blocked_user_id,
        },
    )
    return True


@database_sync_to_async
def list_users(
    event_id,
    page,
    page_size,
    search_term,
    search_fields=None,
    badge=None,
    trait_badges_map=None,
    include_banned=True,
    include_admin_info=False,
) -> object:
    qs = (
        User.objects.filter(
            event_id=event_id,
            show_publicly=True,
            deleted=False,
            type=User.UserType.PERSON,
        )
        .exclude(profile__display_name__isnull=True)
        .exclude(profile__display_name__exact="")
    )
    if not include_banned:
        qs = qs.exclude(moderation_state=User.ModerationState.BANNED)
    if badge:
        conditions = []
        if trait_badges_map:
            for t_trait, t_badge in trait_badges_map.items():
                if t_badge == badge:
                    conditions.append(Q(traits__contains=[t_trait]))
        if conditions:
            qs = qs.filter(reduce(operator.or_, conditions))
        else:
            qs = qs.none()

    if search_term:
        conditions = [(Q(profile__display_name__icontains=search_term))]
        search_fields = search_fields or []
        for field in search_fields:
            conditions.append(
                Q(**{"profile__fields__" + field + "__icontains": search_term})
            )
        qs = qs.filter(reduce(operator.or_, conditions))

    try:
        p = Paginator(
            qs.order_by("profile__display_name").values(
                "id",
                "profile",
                "traits",
                "last_login",
                "moderation_state",
                "token_id",
                "pretalx_id",
                "email",
                "wikimedia_username",
            ),
            page_size,
        ).page(page)
        ticket_by_token = {}
        if include_admin_info and p.object_list:
            tids = [u["token_id"] for u in p.object_list if u.get("token_id")]
            if tids:
                ticket_by_token = build_admin_ticket_rows_by_token(event_id, tids)
        email_to_wikimedia = {}
        if include_admin_info and p.object_list:
            admin_rows = [
                admin_public_fields_from_user_row(u, ticket_by_token)
                for u in p.object_list
            ]
            emails_to_resolve = [
                row["email"]
                for row in admin_rows
                if row.get("email") and not row.get("wikimedia_username")
            ]
            if emails_to_resolve:
                with scopes_disabled():
                    email_to_wikimedia = resolve_wikimedia_usernames_by_email(
                        emails_to_resolve
                    )
        return {
            "results": sorted(
                (
                    dict(
                        id=str(u["id"]),
                        profile=u["profile"],
                        pretalx_id=u["pretalx_id"],
                        inactive=u["last_login"] is None
                        or u["last_login"] < now() - timedelta(hours=36),
                        badges=(
                            sorted(
                                list(
                                    {
                                        badge
                                        for trait, badge in trait_badges_map.items()
                                        if trait in u["traits"]
                                    }
                                )
                            )
                            if trait_badges_map
                            else []
                        ),
                        **(
                            admin_public_fields_with_email_fallback(
                                u,
                                ticket_by_token,
                                email_to_wikimedia,
                            )
                            if include_admin_info
                            else {}
                        ),
                    )
                    for u in p.object_list
                ),
                key=lambda u: (
                    u["profile"]["display_name"].lower(),
                    int(u["inactive"] or 0),
                ),
            ),
            "isLastPage": not p.has_next(),
        }
    except InvalidPage:
        return {
            "results": [],
            "isLastPage": True,
        }


async def user_broadcast(event_type, data, user_id, socket_id):
    await get_channel_layer().group_send(
        GROUP_USER.format(id=user_id),
        {
            "type": "user.broadcast",
            "event_type": event_type,
            "data": data,
            "socket": socket_id,
        },
    )
