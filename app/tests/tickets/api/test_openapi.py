import pytest
from django.conf import settings
from django.test import override_settings
from drf_spectacular.validation import validate_schema
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerSplitView,
)
from rest_framework.test import APIRequestFactory

from eventyay.api.schema import EventyaySchemaGenerator


@pytest.fixture(scope='module')
def openapi_schema():
    with override_settings(DEBUG=False):
        yield EventyaySchemaGenerator().get_schema(request=None, public=True)


def test_openapi_schema_is_valid(openapi_schema):
    validate_schema(openapi_schema)
    assert openapi_schema['info'] == {
        'title': 'eventyay API',
        'version': 'v1',
        'description': 'API for managing eventyay organizers and events.',
    }
    assert openapi_schema['paths']
    assert not any('/ticketlayouts/' in path for path in openapi_schema['paths'])
    assert not any('/ticketlayoutproducts/' in path for path in openapi_schema['paths'])


def test_openapi_organizer_operations(openapi_schema):
    list_operation = openapi_schema['paths']['/api/v1/organizers/']['get']
    assert list_operation['summary'] == 'List Organizers'
    assert {parameter['name'] for parameter in list_operation['parameters']} == {
        'ordering',
        'page',
    }
    assert list_operation['responses']['200']['content']['application/json']['schema'] == {
        '$ref': '#/components/schemas/PaginatedOrganizerList'
    }

    action_responses = {
        'follow': 'OrganizerFollowResponse',
        'unfollow': 'OrganizerUnfollowResponse',
        'followers': 'OrganizerFollowersResponse',
    }
    for action, component in action_responses.items():
        method = 'get' if action == 'followers' else 'post'
        operation = openapi_schema['paths'][f'/api/v1/organizers/{{organizer}}/{action}/'][method]
        assert 'requestBody' not in operation
        assert operation['responses']['200']['content']['application/json']['schema'] == {
            '$ref': f'#/components/schemas/{component}'
        }
        assert {'401', '403'} <= operation['responses'].keys()

    security_schemes = openapi_schema['components']['securitySchemes']
    assert security_schemes['teamTokenAuth']['description'].endswith('`Token <token>` format.')
    assert security_schemes['deviceTokenAuth']['description'].endswith('`Device <token>` format.')
    assert set(security_schemes['oauth2']['flows']['authorizationCode']['scopes']) == {
        'profile',
        'read',
        'write',
    }


def test_openapi_documentation_views():
    factory = APIRequestFactory()
    templates = list(settings.TEMPLATES)
    templates[0] = {
        **templates[0],
        'OPTIONS': {
            **templates[0]['OPTIONS'],
            'context_processors': [],
        },
    }
    with override_settings(DEBUG=False, TEMPLATES=templates):
        schema_response = SpectacularAPIView.as_view(api_version='api-v1')(
            factory.get('/api/v1/schema/', HTTP_ACCEPT='application/json')
        )
        swagger_response = SpectacularSwaggerSplitView.as_view(url_name='api-schema')(
            factory.get('/api/v1/docs/')
        )
        swagger_script_response = SpectacularSwaggerSplitView.as_view(url_name='api-schema')(
            factory.get('/api/v1/docs/', {'script': ''})
        )
        redoc_response = SpectacularRedocView.as_view(url_name='api-schema')(
            factory.get('/api/v1/redoc/')
        )
        for response in (
            schema_response,
            swagger_response,
            swagger_script_response,
            redoc_response,
        ):
            response.render()

    assert schema_response.status_code == 200
    assert schema_response.data['openapi'] == '3.0.3'
    assert swagger_response.status_code == 200
    assert b'swagger-ui' in swagger_response.content
    assert swagger_script_response.status_code == 200
    assert swagger_script_response.content_type == 'application/javascript'
    assert redoc_response.status_code == 200
    assert b'redoc' in redoc_response.content.lower()
