import logging
from functools import wraps
from typing import List

from django.contrib.auth import get_user_model

from django_sso import deauthenticate_user
from datetime import datetime


def acceptor(f):
    """
    Event receiver method decorator. If a method is written to receive events, you must decorate it,
    otherwise the system will not resolve the method as an event handler.

    This is for security reasons that only handlers can be called, not functions.
    """

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        started_at = datetime.now()

        try:
            f(self, *args, **kwargs)
        except Exception as e:
            logging.error(f'Django SSO Error {f.__qualname__}: {e}')

        duration_seconds = (datetime.now() - started_at).total_seconds()

        if duration_seconds >= 1:
            logging.warning(
                f'Django SSO: Execution duration of method {f.__qualname__}'
                f' too long: {duration_seconds:.3f}s'
            )

    wrapper.__is_sso_event_acceptor = True

    return wrapper


class EventAcceptor:
    """
    This class processes all events received from SSO service
    You can override it for change behavior

    Here the method name is equal to the event type. All event handlers must be decorated with @acceptor,
    or they will not be resolved as event receiver methods.
    """

    def _get_user(self, user_identy):
        """
        Get user by USERNAME_FIELD (unique field with always filled user identy)
        By default in Django - username. Name of field stored in USERNAME_FIELD
        """
        return get_user_model().objects.filter(**{
            f'{get_user_model().USERNAME_FIELD}': user_identy
        }).first()

    @acceptor
    def update_account(self, fields: dict):
        """
        Update or create user by identy

        Event fields 'is_active', 'is_staff', 'is_superuser' will cast to bool.

        Args:
            fields (dict): Array of fields for create/update user
        """
        user_model = get_user_model()
        data = {}

        for basic_field in ('is_active', 'is_staff', 'is_superuser'):
            if (
                hasattr(user_model, basic_field)
                and basic_field in fields
            ):
                data[basic_field] = bool(fields[basic_field])

        user_model.objects.update_or_create(**{
            user_model.USERNAME_FIELD: fields['user_identy'],
            'defaults': data
        })

    @acceptor
    def deauthenticate(self, user_identy):
        """
        Process deauthentication event from gateway

        Args:
            user_identy: It's user identy. E-Mail or Login...
        """
        deauthenticate_user(user_identy)

    @acceptor
    def update_fields(self, user_identities: List[str], fields: dict):
        """
        Accepts part of additional fields (sliced per one model)

        @param user_identities: Array of affected user identities
        @param fields: Updated fields, related to the user_identities
        """

    @acceptor
    def delete_user(self, user_identy: str):
        """
        Accepts information about user deletion on the SSO gateway

        @param user_identy
        """
        user = self._get_user(user_identy)

        if not user:
            return

        if hasattr(user, 'is_active') and user.is_active:
            user.is_active = False
            user.save()

    @acceptor
    def change_user_identy(self, old, new):
        """
        Renaming user when on the SSO gateway user identy (username or email or etc...) has been changed.

        @param old: old user identy
        @param new: new user identy
        """
        user = self._get_user(old)

        if user:
            setattr(user, get_user_model().USERNAME_FIELD, new)
            user.save()
