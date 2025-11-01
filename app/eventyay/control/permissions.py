from urllib.parse import quote

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _


def current_url(request):
    if request.GET:
        return request.path + '?' + request.GET.urlencode()
    else:
        return request.path


def event_permission_required(permission):
    """
    This view decorator rejects all requests with a 403 response which are not from
    users having the given permission for the event the request is associated with.
    """
    if permission == 'can_change_settings':
        # Legacy support
        permission = 'can_change_event_settings'

    def decorator(function):
        def wrapper(request, *args, **kw):
            if not request.user.is_authenticated:  # NOQA
                # just a double check, should not ever happen
                raise PermissionDenied()

            allowed = request.user.has_event_permission(request.organizer, request.event, permission, request=request)
            if allowed:
                return function(request, *args, **kw)

            raise PermissionDenied(_('You do not have permission to view this content.'))

        return wrapper

    return decorator


class EventPermissionRequiredMixin:
    """
    This mixin is equivalent to the event_permission_required view decorator but
    is in a form suitable for class-based views.
    """

    permission = ''

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(EventPermissionRequiredMixin, cls).as_view(**initkwargs)
        return event_permission_required(cls.permission)(view)


def organizer_permission_required(permission):
    """
    This view decorator rejects all requests with a 403 response which are not from
    users having the given permission for the event the request is associated with.
    """
    if permission == 'can_change_settings':
        # Legacy support
        permission = 'can_change_organizer_settings'

    def decorator(function):
        def wrapper(request, *args, **kw):
            if not request.user.is_authenticated:  # NOQA
                # just a double check, should not ever happen
                raise PermissionDenied()

            allowed = request.user.has_organizer_permission(request.organizer, permission, request=request)
            if allowed:
                return function(request, *args, **kw)

            raise PermissionDenied(_('You do not have permission to view this content.'))

        return wrapper

    return decorator


class OrganizerPermissionRequiredMixin:
    """
    This mixin is equivalent to the organizer_permission_required view decorator but
    is in a form suitable for class-based views.
    """

    permission = ''

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(OrganizerPermissionRequiredMixin, cls).as_view(**initkwargs)
        return organizer_permission_required(cls.permission)(view)


def administrator_permission_required():
    """
    This view decorator rejects all requests with a 403 response which are not from
    users with a current staff member session.
    """

    def decorator(function):
        def wrapper(request, *args, **kw):
            if not request.user.is_authenticated:  # NOQA
                # just a double check, should not ever happen
                raise PermissionDenied()
            if not request.user.has_active_staff_session(request.session.session_key):
                if request.user.is_staff:
                    return redirect(reverse('control:user.sudo') + '?next=' + quote(current_url(request)))
                raise PermissionDenied(_('You do not have permission to view this content.'))
            return function(request, *args, **kw)

        return wrapper

    return decorator


def staff_member_required():
    """
    This view decorator rejects all requests with a 403 response which are not staff
    members (but do not need to have an active session).
    """

    def decorator(function):
        def wrapper(request, *args, **kw):
            if not request.user.is_authenticated:  # NOQA
                # just a double check, should not ever happen
                raise PermissionDenied()
            if not request.user.is_staff:
                raise PermissionDenied(_('You do not have permission to view this content.'))
            return function(request, *args, **kw)

        return wrapper

    return decorator


class AdministratorPermissionRequiredMixin:
    """
    This mixin is equivalent to the administrator_permission_required view decorator but
    is in a form suitable for class-based views.
    """

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(AdministratorPermissionRequiredMixin, cls).as_view(**initkwargs)
        return administrator_permission_required()(view)


class StaffMemberRequiredMixin:
    """
    This mixin is equivalent to the staff_memer_required view decorator but
    is in a form suitable for class-based views.
    """

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(StaffMemberRequiredMixin, cls).as_view(**initkwargs)
        return staff_member_required()(view)


class OrganizerCreationPermissionMixin:
    """
    Mixin to check if a user has permission to create organizers.
    Can be used in any view that needs to check organizer creation permissions.
    """

    def _can_create_organizer(self, user):
        """
        Check if the user has permission to create an organizer.
        System admins can always create organizers.
        Other users can create organizers based on global settings.
        
        Args:
            user: The user to check permissions for
            
        Returns:
            bool: True if user can create organizers, False otherwise
        """
        from eventyay.base.settings import GlobalSettingsObject
        
        # System admins can always create organizers
        if user.has_active_staff_session(self.request.session.session_key):
            return True

        # Get global settings
        gs = GlobalSettingsObject()
        allow_all_users = gs.settings.get('allow_all_users_create_organizer', None, as_type=bool)
        allow_payment_users = gs.settings.get('allow_payment_users_create_organizer', None, as_type=bool)

        # If neither option is explicitly set, default to allowing all users (permissive default)
        if allow_all_users is None and allow_payment_users is None:
            return True

        # If all users are allowed
        if allow_all_users:
            return True

        # If users with payment information are allowed
        if allow_payment_users:
            return self._user_has_payment_info(user)

        # By default, deny access if settings are explicitly set to False
        return False

    def _user_has_payment_info(self, user):
        """
        Check if the user has valid payment information on file.
        This is determined by checking if any of their organizers have a billing record with stripe_customer_id.
        
        Args:
            user: The user to check payment info for
            
        Returns:
            bool: True if user has payment info, False otherwise
        """
        from eventyay.base.models import Organizer
        from eventyay.base.models.organizer import OrganizerBillingModel
        
        # Get all organizers where the user is a team member
        user_organizers = Organizer.objects.filter(
            teams__members=user
        ).distinct()

        # Check if any of these organizers have billing info with stripe_customer_id
        for organizer in user_organizers:
            billing = OrganizerBillingModel.objects.filter(
                organizer=organizer,
                stripe_customer_id__isnull=False
            ).exclude(stripe_customer_id='').first()
            if billing:
                return True

        return False
