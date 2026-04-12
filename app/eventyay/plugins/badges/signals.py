import copy
import json
from collections import defaultdict

from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Order
from eventyay.base.signals import (
    event_copy_data,
    product_copy_data,
    logentry_display,
    logentry_object_link,
    register_data_exporters,
    register_ticket_outputs,
)
from eventyay.control.signals import (
    nav_event,
    order_info,
    order_position_buttons,
)
from eventyay.presale.signals import question_form_fields

from eventyay.plugins.badges.forms import BadgeOptionsField
from eventyay.plugins.badges.models import BadgeProduct, BadgeLayout
from eventyay.plugins.badges.utils import (
    BADGE_HIDDEN_FIELDS_KEY,
    get_badge_customizable_fields,
    get_badge_hidden_fields,
    get_badge_layout_for_position,
)


@receiver(register_ticket_outputs)
def register_badge_output(sender: Event, **kwargs):
    from .providers import BadgeOutputProvider

    return BadgeOutputProvider


@receiver(nav_event, dispatch_uid='badges_nav')
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    p = request.user.has_event_permission(
        request.organizer, request.event, 'can_change_settings', request
    ) or request.user.has_event_permission(request.organizer, request.event, 'can_view_orders', request)
    if not p:
        return []
    return [
        {
            'label': _('Badges'),
            'url': reverse(
                'plugins:badges:index',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            ),
            'active': url.namespace == 'plugins:badges',
            'icon': 'id-card',
        }
    ]


@receiver(product_copy_data, dispatch_uid='badges_product_copy')
def copy_product(sender, source, target, **kwargs):
    try:
        inst = BadgeProduct.objects.get(product=source)
        BadgeProduct.objects.create(product=target, layout=inst.layout)
    except BadgeProduct.DoesNotExist:
        pass


@receiver(signal=event_copy_data, dispatch_uid='badges_copy_data')
def event_copy_data_receiver(sender, other, question_map, product_map, **kwargs):
    layout_map = {}
    for bl in other.badge_layouts.all():
        oldid = bl.pk
        bl = copy.copy(bl)
        bl.pk = None
        bl.event = sender

        layout = json.loads(bl.layout)
        for o in layout:
            if o['type'] == 'textarea':
                if o['content'].startswith('question_'):
                    newq = question_map.get(int(o['content'][9:]))
                    if newq:
                        o['content'] = 'question_{}'.format(newq.pk)
        ask_user_fields = []
        for field in bl.ask_user_fields_data:
            if field.startswith('question_'):
                newq = question_map.get(int(field[9:]))
                if newq:
                    ask_user_fields.append('question_{}'.format(newq.pk))
            else:
                ask_user_fields.append(field)
        bl.ask_user_fields_data = ask_user_fields
        bl.save()

        if bl.background and bl.background.name:
            bl.background.save('background.pdf', bl.background)

        layout_map[oldid] = bl

    for bi in BadgeProduct.objects.filter(product__event=other):
        BadgeProduct.objects.create(product=product_map.get(bi.product_id), layout=layout_map.get(bi.layout_id))


@receiver(question_form_fields, dispatch_uid='badges_question_form_fields')
def badge_question_form_fields(sender, position, **kwargs):
    layout = get_badge_layout_for_position(sender, position)
    if not layout or not layout.allow_customization:
        return {}

    ask_user_keys = set(layout.ask_user_fields_data)
    choices = [
        (
            field['key'],
            field['sample'] if field['key'].startswith('question_') and field.get('sample') else field['label'],
        )
        for field in get_badge_customizable_fields(sender, layout)
        if field['key'] in ask_user_keys
    ]
    if not choices:
        return {}

    return {
        BADGE_HIDDEN_FIELDS_KEY: BadgeOptionsField(
            label=_('Badge options'),
            choices=choices,
            hidden_initial=get_badge_hidden_fields(position),
        )
    }


@receiver(register_data_exporters, dispatch_uid='badges_export_all')
def register_pdf(sender, **kwargs):
    from .exporters import BadgeExporter

    return BadgeExporter


def _cached_rendermap(event):
    if hasattr(event, '_cached_renderermap'):
        return event._cached_renderermap
    renderermap = {
        bi.product_id: bi.layout_id for bi in BadgeProduct.objects.select_related('layout').filter(product__event=event)
    }
    try:
        default_renderer = event.badge_layouts.get(default=True).pk
    except BadgeLayout.DoesNotExist:
        default_renderer = None
    event._cached_renderermap = defaultdict(lambda: default_renderer)
    event._cached_renderermap.update(renderermap)
    return event._cached_renderermap


@receiver(order_position_buttons, dispatch_uid='badges_control_order_buttons')
def control_order_position_info(sender: Event, position, request, order: Order, **kwargs):
    if _cached_rendermap(sender)[position.product_id] is None:
        return ''
    template = get_template('pretixplugins/badges/control_order_position_buttons.html')
    ctx = {'order': order, 'request': request, 'event': sender, 'position': position}
    return template.render(ctx, request=request).strip()


@receiver(order_info, dispatch_uid='badges_control_order_info')
def control_order_info(sender: Event, request, order: Order, **kwargs):
    cm = _cached_rendermap(sender)
    if all(cm[p.product_id] is None for p in order.positions.all()):
        return ''

    template = get_template('pretixplugins/badges/control_order_info.html')

    ctx = {
        'order': order,
        'request': request,
        'event': sender,
    }
    return template.render(ctx, request=request)


@receiver(signal=logentry_display, dispatch_uid='badges_logentry_display')
def badges_logentry_display(sender, logentry, **kwargs):
    if not logentry.action_type.startswith('eventyay.plugins.badges'):
        return

    plains = {
        'eventyay.plugins.badges.layout.added': _('Badge layout created.'),
        'eventyay.plugins.badges.layout.deleted': _('Badge layout deleted.'),
        'eventyay.plugins.badges.layout.changed': _('Badge layout changed.'),
    }

    if logentry.action_type in plains:
        return plains[logentry.action_type]


@receiver(signal=logentry_object_link, dispatch_uid='badges_logentry_object_link')
def badges_logentry_object_link(sender, logentry, **kwargs):
    if not logentry.action_type.startswith('eventyay.plugins.badges.layout') or not isinstance(
        logentry.content_object, BadgeLayout
    ):
        return

    a_text = _('Badge layout {val}')
    a_map = {
        'href': reverse(
            'plugins:badges:edit',
            kwargs={
                'event': sender.slug,
                'organizer': sender.organizer.slug,
                'layout': logentry.content_object.id,
            },
        ),
        'val': escape(logentry.content_object.name),
    }
    a_map['val'] = '<a href="{href}">{val}</a>'.format_map(a_map)
    return a_text.format_map(a_map)
