from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from eventyay.base.entitlements import EntitlementDecision, check_entitlement


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
