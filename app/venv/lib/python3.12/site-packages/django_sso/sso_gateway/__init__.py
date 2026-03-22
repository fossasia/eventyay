import sys
from inspect import isfunction

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Field
from django.db.models.base import ModelBase
from django.db.models.fields.related_descriptors import (
    ForwardOneToOneDescriptor,
    ForwardManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    DeferredAttribute,
)
from django.utils.translation import gettext_lazy as _

from django_sso.exceptions import SSOException


def set_sso_authorization_request_used(sso_token):
    """
    For sso_service side. Makes SSO request as used for authentication procedure (not available for next authentications)
    """
    try:
        result = requests.post(settings.SSO['ROOT'] + '/sso/make_used/', {
            'token': settings.SSO['TOKEN'],
            'authentication_token': sso_token
        })

        if result.status_code != 200:
            raise Exception(f'Некорректный ответ сервера авторизации: STATUS={result.status_code}; TEXT={result.text}')
    except Exception as e:
        raise SSOException(e)


class Settings:
    """
    The Django SSO settings provider (singleton)
    """

    instance = None
    """
    Instance of SSO settings
    """

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls, *args, **kwargs)

        return cls.instance

    def __init__(self):
        self.affected_models_fields = {}

        if not hasattr(settings, 'SSO'):
            return

        assert type(settings.SSO) == dict, _('SSO settings variable must be dict')
        """
        Models, used in SSO['ADDITIONAL_FIELDS'] parameer mapped to the SSO['ADDITIONAL_FIELDS'] values.
        """

        if 'ADDITIONAL_FIELDS' in settings.SSO:
            self.validate_additional_fields(settings.SSO['ADDITIONAL_FIELDS'])

    def validate_additional_fields(self, fields_list=None):
        """
        Validate SSO[ADDITIONAL_FIELDS] and fill the self.affected_models
        """
        user_model = get_user_model()
        result_field_names = []

        assert type(fields_list) in (list, set, tuple), \
            _('The SSO[ADDITIONAL_FIELDS] setting variable must be list, set or tuple')

        for field in fields_list:
            assert type(field) == str, _('The SSO[ADDITIONAL_FIELDS] members must be str')

            field_info = field.split(':')
            field_path = field_info[0].split('.')
            target = user_model

            result_field_names.append(field_info[0] if len(field_info) == 1 else field_info[1])

            for attribute in field_path:
                if not hasattr(target, attribute):
                    raise Exception(
                        f'Django SSO: Bad field "{field_info[0]}": {target.__class__.__name__} hasnt {attribute}'
                    )

                attribute_ref = getattr(target, attribute)

                if isinstance(attribute_ref, DeferredAttribute):
                    # Any model field
                    target = attribute_ref.field
                elif isinstance(attribute_ref, (ForwardManyToOneDescriptor, ForwardOneToOneDescriptor)):
                    # Any Foreigin or OneToOne relation
                    target = attribute_ref.field.related_model
                elif isinstance(attribute_ref, ReverseOneToOneDescriptor):
                    # Reverse OneToOne relation
                    target = attribute_ref.related.related_model
                elif isfunction(attribute_ref) or isinstance(attribute_ref, property):
                    # Allow methods as data sources and @property's
                    target = attribute_ref
                else:
                    # Reject any other type
                    raise Exception(f'Django SSO: Found bad target \'{attribute_ref}\' for \'{field}\' field')

            # region Getting the model of target field/prop/method.
            if isinstance(target, ModelBase):
                affected_model = target
            elif isinstance(target, Field):
                affected_model = target.model
            elif isfunction(target):
                affected_model = getattr(sys.modules[target.__module__], target.__qualname__.split('.')[0])
            elif isinstance(target, property):
                affected_model = getattr(sys.modules[target.fget.__module__], target.fget.__qualname__.split('.')[0])
            else:
                raise Exception(f'Django SSO: Cant determine the Model of target {target} for "{field_info[0]}"')

            if affected_model not in self.affected_models_fields:
                self.affected_models_fields[affected_model] = []

            self.affected_models_fields[affected_model].append(field)
            # endregion

        # region Check for unique
        assert len(result_field_names) == len(set(result_field_names)), \
            (
                    "Django SSO: SSO[ADDITIONAL_FIELDS] fields/aliases must be distinct. Found duplicates: %s"
                    % (', '.join({f for f in result_field_names if result_field_names.count(f) > 1}))
            )
        # endregion

        # region Check for reserved names
        used_reserved_fields = []

        for reserved_field in ('username', 'is_active', 'is_staff', 'is_superuser'):
            if result_field_names.count(reserved_field) > 0:
                used_reserved_fields.append(reserved_field)

        if len(used_reserved_fields) > 0:
            raise Exception(
                'Django SSO: SSO[ADDITIONAL_FIELDS] uses reserved fields: %s'
                % ', '.join(used_reserved_fields)
            )
        # endregion
