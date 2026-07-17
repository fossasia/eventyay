from django_scopes import scopes_disabled
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.generators import SchemaGenerator


class EventyaySchemaGenerator(SchemaGenerator):
    def __init__(self, *args, api_version=None, **kwargs):
        super().__init__(*args, api_version=api_version or 'api-v1', **kwargs)

    @scopes_disabled()
    def get_schema(self, request=None, public=False):
        return super().get_schema(request=request, public=public)


class TeamTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'eventyay.api.auth.token.TeamTokenAuthentication'
    name = 'teamTokenAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Team API token using the `Token <token>` format.',
        }


class DeviceTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'eventyay.api.auth.device.DeviceTokenAuthentication'
    name = 'deviceTokenAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Device API token using the `Device <token>` format.',
        }


class OAuth2AuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'oauth2_provider.contrib.rest_framework.OAuth2Authentication'
    name = 'oauth2'
    priority = 1

    def get_security_definition(self, auto_schema):
        return {
            'type': 'oauth2',
            'flows': {
                'authorizationCode': {
                    'authorizationUrl': '/api/v1/oauth/authorize',
                    'tokenUrl': '/api/v1/oauth/token',
                    'scopes': {
                        'profile': 'User profile only',
                        'read': 'Read access',
                        'write': 'Write access',
                    },
                },
            },
        }
