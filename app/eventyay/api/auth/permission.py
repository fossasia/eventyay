from rest_framework.permissions import SAFE_METHODS, BasePermission

from eventyay.api.models import OAuthAccessToken
from eventyay.base.models import Device, Event, User
from eventyay.base.models.auth import SuperuserPermissionSet
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.helpers.security import (
    SessionInvalid,
    SessionReauthRequired,
    assert_session_valid,
)


class EventPermission(BasePermission):
    @staticmethod
    def _get_required_permission(request, view):
        if request.method not in SAFE_METHODS and hasattr(view, 'write_permission'):
            return getattr(view, 'write_permission')
        if hasattr(view, 'permission'):
            return getattr(view, 'permission')
        return None

    @staticmethod
    def _has_required_permission(required_permission, permission_set):
        if isinstance(required_permission, (list, tuple)):
            return any(permission in permission_set for permission in required_permission)
        return not required_permission or required_permission in permission_set

    @staticmethod
    def _resolve_event(event_slug, organizer_slug=None):
        lookup = {'slug__iexact': event_slug}
        if organizer_slug:
            lookup['organizer__slug__iexact'] = organizer_slug

        event = Event.objects.filter(**lookup).select_related('organizer').first()
        if event or not str(event_slug).isdigit():
            return event

        lookup = {'pk': int(event_slug)}
        if organizer_slug:
            lookup['organizer__slug__iexact'] = organizer_slug
        return Event.objects.filter(**lookup).select_related('organizer').first()

    @staticmethod
    def _set_eventpermset(request, perm_holder):
        if isinstance(perm_holder, User) and perm_holder.has_active_staff_session(
            request.session.session_key
        ):
            request.eventpermset = SuperuserPermissionSet()
        else:
            request.eventpermset = perm_holder.get_event_permission_set(
                request.organizer, request.event
            )

    def _has_event_permission(
        self, request, perm_holder, required_permission, event_slug, organizer_slug=None
    ):
        request.event = self._resolve_event(event_slug, organizer_slug=organizer_slug)
        if not request.event:
            return False
        if not perm_holder.has_event_permission(
            request.event.organizer, request.event, request=request
        ):
            return False

        request.organizer = request.event.organizer
        self._set_eventpermset(request, perm_holder)
        return self._has_required_permission(required_permission, request.eventpermset)

    def has_permission(self, request, view):
        if not request.user.is_authenticated and not isinstance(request.auth, (Device, TeamAPIToken)):
            return False

        required_permission = self._get_required_permission(request, view)

        if request.user.is_authenticated:
            try:
                # If this logic is updated, make sure to also update the logic in eventyay/control/middleware.py
                assert_session_valid(request)
            except SessionInvalid:
                return False
            except SessionReauthRequired:
                return False

        perm_holder = request.auth if isinstance(request.auth, (Device, TeamAPIToken)) else request.user
        kwargs = request.resolver_match.kwargs
        if 'event' in kwargs:
            if not self._has_event_permission(
                request,
                perm_holder,
                required_permission,
                event_slug=kwargs['event'],
                organizer_slug=kwargs.get('organizer'),
            ):
                return False
        elif 'organizer' in kwargs:
            if not request.organizer or not perm_holder.has_organizer_permission(request.organizer, request=request):
                return False
            if isinstance(perm_holder, User) and perm_holder.has_active_staff_session(request.session.session_key):
                request.orgapermset = SuperuserPermissionSet()
            else:
                request.orgapermset = perm_holder.get_organizer_permission_set(request.organizer)
            if not self._has_required_permission(required_permission, request.orgapermset):
                return False

        if isinstance(request.auth, OAuthAccessToken):
            if not request.auth.allow_scopes(['write']) and request.method not in SAFE_METHODS:
                return False
            if not request.auth.allow_scopes(['read']) and request.method in SAFE_METHODS:
                return False
        if isinstance(request.auth, OAuthAccessToken) and hasattr(request, 'organizer'):
            if not request.auth.organizers.filter(pk=request.organizer.pk).exists():
                return False
        return True


class EventCRUDPermission(EventPermission):
    def has_permission(self, request, view):
        if not super(EventCRUDPermission, self).has_permission(request, view):
            return False
        elif view.action == 'create' and 'can_create_events' not in request.orgapermset:
            return False
        elif view.action == 'destroy' and 'can_change_event_settings' not in request.eventpermset:
            return False
        elif view.action in ['update', 'partial_update'] and 'can_change_event_settings' not in request.eventpermset:
            return False

        return True


class CloneEventPermission(EventPermission):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        if request.method in SAFE_METHODS:
            return True

        perm_holder = request.auth if isinstance(request.auth, (Device, TeamAPIToken)) else request.user
        if isinstance(perm_holder, User) and perm_holder.has_active_staff_session(request.session.session_key):
            request.orgapermset = SuperuserPermissionSet()
        else:
            request.orgapermset = perm_holder.get_organizer_permission_set(request.organizer)

        return 'can_create_events' in request.orgapermset


class ProfilePermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated and not isinstance(request.auth, (Device, TeamAPIToken)):
            return False

        if request.user.is_authenticated:
            try:
                # If this logic is updated, make sure to also update the logic in eventyay/control/middleware.py
                assert_session_valid(request)
            except SessionInvalid:
                return False
            except SessionReauthRequired:
                return False

        if isinstance(request.auth, OAuthAccessToken):
            if (
                not (request.auth.allow_scopes(['read']) or request.auth.allow_scopes(['profile']))
                and request.method in SAFE_METHODS
            ):
                return False

        return True


class AnyAuthenticatedClientPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated and not isinstance(request.auth, (Device, TeamAPIToken)):
            return False

        if request.user.is_authenticated:
            try:
                # If this logic is updated, make sure to also update the logic in eventyay/control/middleware.py
                assert_session_valid(request)
            except SessionInvalid:
                return False
            except SessionReauthRequired:
                return False

        return True
