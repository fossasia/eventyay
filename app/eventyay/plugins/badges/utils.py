import json

from django.utils.translation import gettext_lazy as _

from eventyay.base.pdf import get_variables

from .models import BadgeLayout, BadgeProduct


BADGE_HIDDEN_FIELDS_KEY = 'badge_hidden_fields'


def clear_badge_layout_cache(event):
    for attr in ('_badge_layout_assignment_map', '_default_badge_layout', '_cached_renderermap'):
        if hasattr(event, attr):
            delattr(event, attr)


def normalize_badge_content_key(content):
    return 'event_name' if content == 'item' else content


def get_badge_layout_assignment_map(event):
    if hasattr(event, '_badge_layout_assignment_map'):
        return event._badge_layout_assignment_map, event._default_badge_layout

    assignment_map = {
        assignment.product_id: assignment.layout
        for assignment in BadgeProduct.objects.select_related('layout').filter(product__event=event)
    }
    try:
        default_layout = event.badge_layouts.get(default=True)
    except BadgeLayout.DoesNotExist:
        default_layout = None

    event._badge_layout_assignment_map = assignment_map
    event._default_badge_layout = default_layout
    return assignment_map, default_layout


def get_badge_layout_for_product(event, product):
    assignment_map, default_layout = get_badge_layout_assignment_map(event)
    product_id = getattr(product, 'pk', product)
    if product_id in assignment_map:
        return assignment_map[product_id]
    return default_layout


def get_badge_layout_for_position(event, position):
    return get_badge_layout_for_product(event, position.product_id)


def get_badge_hidden_fields(position):
    hidden_fields = position.meta_info_data.get('question_form_data', {}).get(BADGE_HIDDEN_FIELDS_KEY, [])
    if isinstance(hidden_fields, str):
        return [hidden_fields]
    return hidden_fields


def get_badge_customizable_fields(event, layout):
    if not layout:
        return []

    if isinstance(layout, BadgeLayout) and hasattr(layout, '_badge_customizable_fields_cache'):
        return layout._badge_customizable_fields_cache

    if isinstance(layout, BadgeLayout):
        layout_data = layout.layout_data
    elif isinstance(layout, str):
        try:
            layout_data = json.loads(layout)
        except ValueError:
            return []
    else:
        layout_data = layout

    if not isinstance(layout_data, list):
        return []

    variables = get_variables(event)
    fields = []
    seen_keys = set()
    for obj in layout_data:
        if not isinstance(obj, dict) or obj.get('type') not in ('text', 'textarea'):
            continue

        content = normalize_badge_content_key(obj.get('content'))
        if not content or content in ('other', 'other_i18n') or content in seen_keys:
            continue

        variable = variables.get(content, {})
        label = variable.get('label') or _badge_field_fallback_label(content)
        fields.append(
            {
                'key': content,
                'label': str(label),
                'sample': str(variable.get('editor_sample') or obj.get('text') or ''),
            }
        )
        seen_keys.add(content)

    if isinstance(layout, BadgeLayout):
        layout._badge_customizable_fields_cache = fields
    return fields


def get_badge_visible_field_labels(event, position, hidden_fields=None):
    layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        return []

    ask_user_keys = set(layout.ask_user_fields_data)
    hidden_fields = {
        str(value) for value in (hidden_fields if hidden_fields is not None else get_badge_hidden_fields(position))
    }
    return [
        field['label']
        for field in get_badge_customizable_fields(event, layout)
        if field['key'] in ask_user_keys and field['key'] not in hidden_fields
    ]


def _badge_field_fallback_label(content):
    if content.startswith('question_'):
        return _('Question')
    if content.startswith('meta:'):
        return _('Event meta: {key}').format(key=content[5:])
    if content.startswith('itemmeta:'):
        return _('Product meta: {key}').format(key=content[9:])
    return content.replace('_', ' ').replace(':', ' - ').title()
