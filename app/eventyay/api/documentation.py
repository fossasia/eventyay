from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from eventyay.base.models.mail import MailTemplateRoles


def exclude_unmigrated_plugin_endpoints(endpoints):
    # These plugin serializers still reference fields from before the Product rename.
    excluded_segments = ('/ticketlayouts/', '/ticketlayoutproducts/')
    return [
        endpoint
        for endpoint in endpoints
        if not any(segment in endpoint[0] for segment in excluded_segments)
    ]


def build_expand_docs(*params):
    description = 'Select fields to <a href="https://docs.pretalx.org/api/fundamentals/#expanding-linked-resources">expand</a>.'
    return OpenApiParameter(
        name='expand',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description=description,
        enum=params,
        many=True,
    )


def build_search_docs(*params, extra_description=None):
    fields = ','.join([f'`"{param}"`' for param in params])
    description = f'A search term, searching in {fields}.'
    if extra_description:
        description = f'{description} {extra_description}'
    return OpenApiParameter(
        name='q',
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        description=description,
    )


def postprocess_schema(result, generator, request, public):
    result['info']['version'] = 'v1'
    schemas = result.setdefault('components', {}).setdefault('schemas', {})
    mail_template = schemas.get('MailTemplate')
    if mail_template and 'role' in mail_template.get('properties', {}):
        schemas['RoleEnum'] = {
            'enum': list(dict(MailTemplateRoles.choices).keys()),
            'type': 'string',
            'description': '\n'.join(
                [f'* `{key}` - {value}' for key, value in MailTemplateRoles.choices]
            ),
        }
        mail_template['properties']['role'] = {
            'nullable': True,
            '$ref': '#/components/schemas/RoleEnum',
        }

    tag_descriptions = {
        'organizers': (
            'Organizer endpoints expose organizers available to the authenticated '
            'user or API credential.'
        ),
    }
    tag_names = []
    for path in result.get('paths', {}).values():
        for operation in path.values():
            if not isinstance(operation, dict):
                continue
            for tag in operation.get('tags', []):
                if tag not in tag_names:
                    tag_names.append(tag)

    result['tags'] = [
        {
            'name': tag,
            **({'description': tag_descriptions[tag]} if tag in tag_descriptions else {}),
        }
        for tag in tag_names
    ]
    return result
