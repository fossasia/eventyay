import logging
from inspect import ismethod, isfunction
from typing import Union

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import QuerySet
from django.db.models.base import ModelBase
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from django_sso.exceptions import SSOException
from django_sso.sso_gateway import Settings

user_model = get_user_model()


def service_token_generator():
    return get_random_string(Service.token.field.max_length)


class Service(models.Model):
    name = models.CharField(max_length=128, verbose_name=_('Name'))
    base_url = models.URLField(verbose_name=_('Base url'))
    enabled = models.BooleanField(default=False, verbose_name=_('Enabled'))
    token = models.CharField(max_length=128, verbose_name=_('Token'), unique=True, default=service_token_generator)

    def __str__(self):
        return self.base_url

    def _send_event(self, event_type, data):
        text = None
        fail = False

        if hasattr(settings, 'SSO_SUBORDINATE_COMMUNICATION_TIMEOUT'):
            timeout = settings.SSO_SUBORDINATE_COMMUNICATION_TIMEOUT

            assert type(settings.SSO_SUBORDINATE_COMMUNICATION_TIMEOUT) in (int, float)
        else:
            timeout = 0.1  # 100ms

        try:
            result = requests.post(
                f'{self.base_url}/sso/event/',
                json={
                    'type': event_type,
                    'token': self.token,
                    **data
                },
                headers={
                    "Content-Type": "application/json"
                },
                timeout=timeout
            )
        except Exception as e:
            logging.error(f"Django SSO: {_('Failed to communicate with subordinated service')} {self.base_url}: {e}")

            return

        try:
            assert result.status_code == 200, f"{result.text}"
            data = result.json()

            ok = not not (data['ok'] if 'ok' in data else False)

            if ok:
                return ok
            elif 'error' in data:
                raise Exception(f"Django SSO: {_('Error raised on subordinate service')}: {data['error']}")
            else:
                raise Exception(result.text)
        except Exception as e:
            logging.error(f'{_("Incorrect response from subordinated service")}: STATUS={result.status_code}; TEXT={e}')

            return

    @staticmethod
    def build_update_user_event(user):
        """
        Build event for accounts update on subbordinated services

        Args:
            user: AbstractBaseUser based classes are allowed
        """
        event = {
            'fields': {}
        }

        for field in ('is_active', 'is_staff', 'is_superuser'):
            if hasattr(user_model, field):
                event['fields'][field] = bool(getattr(user, field))

        event['fields']["user_identy"] = getattr(user, user_model.USERNAME_FIELD)

        if hasattr(settings, 'SSO') and 'ADDITIONAL_FIELDS' in settings.SSO:
            for additional_field in settings.SSO['ADDITIONAL_FIELDS']:
                field_info = additional_field.split(':')
                alias = field_info[1] if len(field_info) == 2 else None

                result = user

                try:
                    for prop in field_info[0].split('.'):
                        try:
                            value = getattr(result, prop)
                        except ObjectDoesNotExist:
                            value = None
                            break

                        if value != None:
                            result = value
                        else:
                            result = None
                            break

                    if ismethod(result):
                        result = result()
                    elif isinstance(result, models.Model):
                        if hasattr(result, 'to_sso_representation'):
                            result = result.to_sso_representation()
                        else:
                            result = str(result)
                except Exception as e:
                    logging.warning('Django SSO: failed to read value for field %s: %s' % (field_info[0], e))
                    result = None

                event['fields'][alias if alias else additional_field] = result

        return event

    @staticmethod
    def build_update_fields_event(user_identities: Union[set, QuerySet], instance: ModelBase):
        """
        Build event for fields update on subbordinated services. Fields of related model.

        Args:
            user_identities: QuerySet with users
            instance: An updated related model
        """

        sso_settings = Settings()

        event = {
            "fields": {},
            "user_identities": (
                [*user_identities.values_list(get_user_model().USERNAME_FIELD, flat=True)]
                if isinstance(user_identities, QuerySet)
                else user_identities
            )
        }

        for field_info in sso_settings.affected_models_fields[instance.__class__]:
            field_info = field_info.split(':')
            field_alias = field_info[1] if len(field_info) == 2 else None
            field_path = field_info[0].split('.')
            field_name = field_alias if field_alias else field_info[0]

            if instance:
                if len(field_path) == 1:
                    if hasattr(instance, 'to_sso_representation'):
                        value = instance.to_sso_representation()
                    else:
                        value = str(instance)
                elif len(field_path) == 2:
                    model_attr = getattr(instance, field_path[1])

                    if model_attr is None:
                        value = None
                    elif ismethod(model_attr):
                        value = model_attr()
                    elif isinstance(model_attr, property):
                        value = model_attr
                    else:
                        value = model_attr
                else:
                    logging.error('Django SSO: Unhandled exception. Contact developer with information about it.')

                if type(value) not in (str, bool, float, int):
                    logging.error(
                        f"Django SSO: For additional field '{field_info}' provided unsupported type {type(value)}"
                    )
                    value = None

                event['fields'][field_name] = value
            else:
                event['fields'][field_name] = None

        return event

    def deauthenticate(self, user: Union[str, ModelBase]):
        """
        Send deauthentication event to subordinate service, if that active

        Args:
            user: User model object or user identy - username field value
        """
        if not self.enabled:
            return True

        return self._send_event('deauthenticate', {
            'user_identy': user if type(user) == str else getattr(user, user_model.USERNAME_FIELD)
        })

    def delete_user(self, user: Union[ModelBase, str]):
        """
        Casts user deletion event

        @param user: User identy string or UserModel instance
        """
        return self._send_event('delete_user', {
            'user_identy': user if isinstance(user, str) else getattr(user, user_model.USERNAME_FIELD)
        })

    def change_user_identy(self, old, new):
        """
        Emit event for changing user identy.

        In cases, when you change login|email|etc...

        @param old: Old user identy
        @param new: New user identy
        """
        return self._send_event('change_user_identy', {
            'old': old,
            'new': new
        })

    def update_account(self, user) -> bool:
        """
        Send account information to subordinated service, if subordinated service is active
        """
        if not self.enabled:
            return True

        return self._send_event(
            event_type='update_account',
            data=self.build_update_user_event(user)
        )

    def update_fields(self, to_users: Union[QuerySet, set], instance: ModelBase = None) -> bool:
        """
        Send event with updated fields of the related model, if subordinated service is active
        """
        if not self.enabled or not len(to_users):
            return True

        return self._send_event(
            event_type='update_fields',
            data=self.build_update_fields_event(to_users, instance)
        )

    @staticmethod
    def cast_event_to_all_services(event_name: str, **kwargs):
        assert len(event_name) and not event_name.startswith('_'), f"Bad event name {event_name}"

        if not hasattr(Service, event_name) or not isfunction(getattr(Service, event_name)):
            raise Exception(f'Django SSO: {Service.__class__.__name__} has no method {event_name}')

        for service in Service.objects.filter(enabled=True):
            getattr(service, event_name)(**kwargs)

    class Meta:
        verbose_name = _('Subordinated service')
        verbose_name_plural = _('Subordinated services')


def auth_token_generator():
    return get_random_string(AuthenticationRequest.token.field.max_length)


class AuthenticationRequest(models.Model):
    service: Service = models.ForeignKey('Service', on_delete=models.CASCADE, verbose_name=_('Service'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    token = models.CharField(max_length=128, verbose_name=_('Token'), default=auth_token_generator, unique=True)
    user_identy = models.CharField(max_length=128, verbose_name=_('User identy'), help_text=_('E-Mail, login, etc.'))
    next_url = models.CharField(max_length=512, verbose_name=_('Next url'), help_text=_('To go after success auth'))
    authenticated = models.BooleanField(default=False, verbose_name=_('Request has been activated'))
    used = models.BooleanField(default=False, verbose_name=_('Are used in external sso service'))

    class Meta:
        verbose_name = _('Authentication request')
        verbose_name_plural = _('Authentication requests')

    def activate(self, user: User):
        """
        1) Activate authentication request
        2) Send base information about user to subordinated service
        """
        self.user_identy = getattr(user, user_model.USERNAME_FIELD)
        self.authenticated = True
        self.save()

        try:
            return self.service.update_account(user)
        except Exception as e:
            raise SSOException(str(e))

    def __str__(self):
        return f'{_("Authenticate")} {self.user_identy} {_("on")} {self.service} {_("then go to")} {self.next_url}'
