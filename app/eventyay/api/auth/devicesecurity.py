from django.utils.translation import gettext_lazy as _


class FullAccessSecurityProfile:
    identifier = 'full'
    verbose_name = _('Full device access')
    usage_description = _(
        'Lead scanning, legacy integrations, and any API feature not covered by the restricted profiles below.'
    )

    def is_allowed(self, request):
        return True


class AllowListSecurityProfile:
    allowlist = ()
    includes_profiles = ()

    @staticmethod
    def _request_keys(request):
        resolver_match = request.resolver_match
        if not resolver_match or not resolver_match.url_name:
            return []

        keys = []
        url_name = resolver_match.url_name
        namespace = resolver_match.namespace or ''

        if namespace:
            keys.append((request.method, f'{namespace}:{url_name}'))
            namespace_parts = namespace.split(':')
            for index in range(len(namespace_parts)):
                ns = ':'.join(namespace_parts[index:])
                keys.append((request.method, f'{ns}:{url_name}'))
        keys.append((request.method, url_name))
        return keys

    @classmethod
    def _request_in_allowlist(cls, request, allowlist):
        return any(key in allowlist for key in cls._request_keys(request))

    def is_allowed(self, request):
        if self._request_in_allowlist(request, self.allowlist):
            return True
        for profile_id in self.includes_profiles:
            profile = DEVICE_SECURITY_PROFILES.get(profile_id)
            if profile and isinstance(profile, AllowListSecurityProfile):
                if profile.is_allowed(request):
                    return True
        return False


# Shared check-in / badge station API surface (scan, search, edit, badges).
_CHECKIN_CORE_ALLOWLIST = (
    ('GET', 'api-v1:version'),
    ('GET', 'api-v1:device.session'),
    ('GET', 'api-v1:device.eventselection'),
    ('POST', 'api-v1:device.update'),
    ('POST', 'api-v1:device.verify-setup-token'),
    ('POST', 'api-v1:device.revoke'),
    ('POST', 'api-v1:device.roll'),
    ('GET', 'api-v1:events-list'),
    ('GET', 'api-v1:events-detail'),
    ('GET', 'api-v1:subevents-list'),
    ('GET', 'api-v1:subevents-detail'),
    ('GET', 'api-v1:question-list'),
    ('GET', 'api-v1:question-detail'),
    ('GET', 'api-v1:checkinlist-list'),
    ('GET', 'api-v1:checkinlist-detail'),
    ('GET', 'api-v1:checkinlist-status'),
    ('GET', 'api-v1:checkinlistpos-list'),
    ('POST', 'api-v1:checkinlistpos-redeem'),
    ('POST', 'api-v1:checkin.redeem'),
    ('GET', 'api-v1:orderposition-list'),
    ('GET', 'api-v1:orderposition-detail'),
    ('PATCH', 'api-v1:orderposition-detail'),
    ('GET', 'api-v1:orderposition-download'),
    ('GET', 'api-v1:orderposition-answer'),
    ('GET', 'api-v1:order-detail'),
    ('GET', 'api-v1:order-download'),
    ('POST', 'api-v1:upload'),
    ('GET', 'badges:api-badge-download'),
    ('GET', 'plugins:badges:api-badge-download'),
)

# Badge Station (kiosk): scan, check-in, search, badge download.
_BADGE_STATION_ALLOWLIST = _CHECKIN_CORE_ALLOWLIST

# Check-In Staff: Badge Station capabilities plus live registration.
_CHECKIN_STAFF_EXTRA_ALLOWLIST = (
    ('GET', 'api-v1:product-list'),
    ('POST', 'api-v1:order-list'),
    ('POST', 'api-v1:order-mark-paid'),
)


class EventyayCheckinSecurityProfile(AllowListSecurityProfile):
    identifier = 'eventyay_checkin'
    verbose_name = _('Check-In Staff')
    usage_description = _(
        'Ticket check-in, attendee search and edits, live registration, and badge printing.'
    )
    includes_profiles = ('eventyay_checkin_online_kiosk',)
    allowlist = _CHECKIN_CORE_ALLOWLIST + _CHECKIN_STAFF_EXTRA_ALLOWLIST


class EventyayCheckinNoSyncSecurityProfile(AllowListSecurityProfile):
    identifier = 'eventyay_checkin_online_kiosk'
    verbose_name = _('Badge Station (kiosk)')
    usage_description = _(
        'Kiosk badge printing: scan tickets, check in attendees, and print badges. No live registration.'
    )
    allowlist = _BADGE_STATION_ALLOWLIST


DEVICE_SECURITY_PROFILES = {
    k.identifier: k()
    for k in (
        FullAccessSecurityProfile,
        EventyayCheckinSecurityProfile,
        EventyayCheckinNoSyncSecurityProfile,
    )
}
