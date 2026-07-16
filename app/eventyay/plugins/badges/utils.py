import json

from django.utils.translation import gettext_lazy as _

from eventyay.base.pdf import get_variables

from .models import BadgeLayout, BadgeProduct


BADGE_HIDDEN_FIELDS_KEY = 'badge_hidden_fields'
BADGE_TICKET_PROVIDER = 'badge'

_renderer_cache = {}


def get_badge_layout_version(event):
    """
    Return the current badge layout/rendering cache version for this event.

    This is stored in the shared (cross-process/cross-worker) cache backend, so every
    Celery worker and web worker will observe a version bump immediately on their next
    lookup, no matter which process actually saved the layout change.
    """
    return event.cache.get('badge_layout_version') or 0


def clear_badge_layout_cache(event):
    for attr in ('_badge_layout_assignment_map', '_default_badge_layout', '_cached_renderermap'):
        if hasattr(event, attr):
            delattr(event, attr)

    # Bump the layout version in the cross-process cache so every worker's in-memory
    # renderer cache is invalidated on its very next use, without needing to reach into
    # other processes' memory.
    version = get_badge_layout_version(event)
    event.cache.set('badge_layout_version', version + 1, 3600 * 24 * 30)

    keys_to_delete = [k for k in _renderer_cache if k[0] == event.pk]
    for k in keys_to_delete:
        del _renderer_cache[k]


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


def product_has_badge_layout_assigned(event, product):
    assignment_map, _ = get_badge_layout_assignment_map(event)
    product_id = getattr(product, 'pk', product)
    if product_id not in assignment_map:
        return False
    return assignment_map[product_id] is not None


def get_badge_layout_for_product(event, product):
    assignment_map, default_layout = get_badge_layout_assignment_map(event)
    product_id = getattr(product, 'pk', product)
    if product_id in assignment_map:
        return assignment_map[product_id]
    return default_layout


def get_badge_layout_for_position(event, position):
    return get_badge_layout_for_product(event, position.product_id)


def get_badge_hidden_fields(position):
    config_position = get_badge_config_position(position)
    root_question_form_data = config_position.meta_info_data.get('question_form_data', {})
    if BADGE_HIDDEN_FIELDS_KEY in root_question_form_data:
        hidden_fields = root_question_form_data[BADGE_HIDDEN_FIELDS_KEY]
    else:
        hidden_fields = position.meta_info_data.get('question_form_data', {}).get(BADGE_HIDDEN_FIELDS_KEY, [])
    if isinstance(hidden_fields, str):
        return [hidden_fields]
    return hidden_fields


def invalidate_badge_cache_for_position(position):
    from eventyay.base.models import CachedCombinedTicket, CachedTicket

    CachedTicket.objects.filter(order_position=position, provider=BADGE_TICKET_PROVIDER).delete()
    order_id = getattr(position, 'order_id', None)
    if order_id:
        CachedCombinedTicket.objects.filter(order=order_id, provider=BADGE_TICKET_PROVIDER).delete()


def invalidate_badge_cache_for_order(order):
    from eventyay.base.models import CachedCombinedTicket, CachedTicket

    CachedTicket.objects.filter(order_position__order=order, provider=BADGE_TICKET_PROVIDER).delete()
    CachedCombinedTicket.objects.filter(order=order, provider=BADGE_TICKET_PROVIDER).delete()


def get_badge_bundle_root(position):
    return position.addon_to if position.addon_to_id else position


def get_badge_config_position(position):
    return get_badge_bundle_root(position)


def get_badge_bundle_positions(position):
    root = get_badge_bundle_root(position)
    return [root, *list(root.addons.all())]


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


def get_badge_bundle_option_choices(event, position):
    """
    Return all configurable badge choices for one attendee bundle.

    The bundle is defined as a base position plus all attached add-ons.
    Choices are deduplicated by key while preserving discovery order.
    """
    seen_keys = set()
    choices = []
    for bundle_position in get_badge_bundle_positions(position):
        if not product_has_badge_layout_assigned(event, bundle_position.product_id):
            continue

        layout = get_badge_layout_for_position(event, bundle_position)
        if not layout or not layout.allow_customization:
            continue

        ask_user_keys = set(layout.ask_user_fields_data)
        for field in get_badge_customizable_fields(event, layout):
            if field['key'] not in ask_user_keys or field['key'] in seen_keys:
                continue
            choices.append(
                (
                    field['key'],
                    field['sample'] if field['key'].startswith('question_') and field.get('sample') else field['label'],
                )
            )
            seen_keys.add(field['key'])
    return choices


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


def get_badge_visible_field_values(event, position, hidden_fields=None):
    layout = get_badge_layout_for_position(event, position)
    if not layout or not layout.allow_customization:
        return []

    ask_user_keys = set(layout.ask_user_fields_data)
    hidden_fields = {
        str(value) for value in (hidden_fields if hidden_fields is not None else get_badge_hidden_fields(position))
    }
    
    variables = get_variables(event)
    
    values = []
    for field in get_badge_customizable_fields(event, layout):
        if field['key'] in ask_user_keys and field['key'] not in hidden_fields:
            if field['key'] in variables:
                try:
                    val = variables[field['key']]['evaluate'](position, position.order, event)
                    if val:
                        values.append(str(val))
                except Exception:
                    pass
    return values


def _badge_field_fallback_label(content):
    if content.startswith('question_'):
        return _('Question')
    if content.startswith('meta:'):
        return _('Event meta: {key}').format(key=content[5:])
    if content.startswith('itemmeta:'):
        return _('Product meta: {key}').format(key=content[9:])
    return content.replace('_', ' ').replace(':', ' - ').title()
