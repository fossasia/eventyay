from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext as _

from eventyay.base.entitlements import EntitlementDecision, check_entitlement
from eventyay.base.models import Organizer
from eventyay.base.models.room import RoomView


JITSI_CONCURRENT_ROOMS_CAPABILITY = 'video.jitsi.concurrent_rooms'
JITSI_MODULE_FILTER = [{'type': 'call.jitsi'}]

VIDEO_MODULE_CAPABILITIES = {
    'livestream.youtube': 'video.youtube',
    'call.jitsi': 'video.jitsi',
    'call.loungemesh': 'video.loungemesh',
    'channel.loungemesh': 'video.loungemesh',
}


def check_video_entitlements(event, module_config) -> EntitlementDecision:
    """Check the organizer's plan, regardless of the attendee or room moderator."""
    capabilities = {
        VIDEO_MODULE_CAPABILITIES[module['type']]
        for module in module_config or []
        if isinstance(module, dict) and module.get('type') in VIDEO_MODULE_CAPABILITIES
    }
    for capability in sorted(capabilities):
        decision = check_entitlement(event.organizer, capability, event=event)
        if not decision.allowed:
            return decision
    return EntitlementDecision(allowed=True)


def require_video_entitlements(event, module_config) -> None:
    """Raise ValidationError if video capabilities are denied by the organizer's plan."""
    decision = check_video_entitlements(event, module_config)
    if not decision.allowed:
        raise ValidationError(
            decision.message or _('Your plan does not include this video feature.'),
            code='entitlement_denied',
        )


def filter_stream_by_entitlement(event, data):
    """Filter after reading the stream cache so plan changes are not cached."""
    if data and data.get('stream_type') == 'youtube':
        if not check_video_entitlements(event, [{'type': 'livestream.youtube'}]).allowed:
            return None
    return data


def running_jitsi_room_ids(organizer, exclude_room=None) -> set:
    """
    Return the organizer's rooms that have someone admitted to their Jitsi call.

    Only rooms that still use Jitsi count. Soft-deleted rooms keep counting while
    admitted participants remain, since deleting a room does not end the call.
    """
    views = RoomView.objects.filter(
        room__event__organizer=organizer,
        room__module_config__contains=JITSI_MODULE_FILTER,
        end__isnull=True,
        jitsi_joined_at__isnull=False,
    )
    if exclude_room is not None:
        views = views.exclude(room=exclude_room)
    return set(views.values_list('room_id', flat=True).distinct())


def not_in_room_decision() -> EntitlementDecision:
    return EntitlementDecision(
        allowed=False,
        reason_code='not_in_room',
        message=_('Enter the room before joining its video call.'),
    )


def _lock_organizer(organizer_id) -> None:
    """Serialize admission changes for one organizer."""
    Organizer.objects.select_for_update().filter(pk=organizer_id).first()


def admit_to_jitsi_room(room, user, view=None) -> EntitlementDecision:
    """
    Admit ``user`` to the Jitsi call of ``room`` within the organizer's room limit.

    Joining a call that is already running is always allowed. Starting a call
    checks ``video.jitsi.concurrent_rooms`` with the total number of running
    Jitsi rooms across the organizer's events, including this one. When allowed,
    the user's open view of the room is marked as admitted so the room counts as
    running until everyone admitted has left. Pass ``view`` to admit only the
    calling connection's view.
    """
    event = room.event
    organizer = event.organizer
    with transaction.atomic():
        _lock_organizer(organizer.pk)
        user_views = RoomView.objects.filter(room=room, user=user, end__isnull=True)
        if view is not None:
            user_views = user_views.filter(pk=view.pk)
        if not user_views.exists():
            return not_in_room_decision()
        already_running = RoomView.objects.filter(
            room=room, end__isnull=True, jitsi_joined_at__isnull=False
        ).exists()
        decision = EntitlementDecision(allowed=True)
        if not already_running:
            running_elsewhere = len(running_jitsi_room_ids(organizer, exclude_room=room))
            decision = check_entitlement(
                organizer,
                JITSI_CONCURRENT_ROOMS_CAPABILITY,
                event=event,
                quantity=running_elsewhere + 1,
            )
            if not decision.allowed:
                return decision
        user_views.filter(jitsi_joined_at__isnull=True).update(jitsi_joined_at=now())
    return decision


def release_jitsi_room(room, user, view=None) -> None:
    """
    Stop counting ``user`` in the Jitsi call of ``room`` after they leave the call.

    Pass ``view`` to release only the calling connection's view, so another browser
    of the same user that is still in the call keeps the room counted.
    """
    with transaction.atomic():
        _lock_organizer(room.event.organizer_id)
        views = RoomView.objects.filter(
            room=room, user=user, end__isnull=True, jitsi_joined_at__isnull=False
        )
        if view is not None:
            views = views.filter(pk=view.pk)
        views.update(jitsi_joined_at=None)


def carry_jitsi_admission(room, user, previous_views) -> bool:
    """
    Return whether a replacement view should stay admitted to the room's Jitsi call.

    Checked under the organizer lock so a concurrent ``jitsi.leave`` cannot be
    undone by the replacement view.
    """
    if not previous_views.filter(jitsi_joined_at__isnull=False).exists():
        return False
    _lock_organizer(room.event.organizer_id)
    return previous_views.filter(jitsi_joined_at__isnull=False).exists()
