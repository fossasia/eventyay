import copy
import json

from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event, Order
from eventyay.base.pdf import remap_question_content_key
from eventyay.base.signals import (
    event_copy_data,
    layout_text_variables,
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
from eventyay.plugins.badges.models import BadgeProduct, BadgeLayout, BadgeVoucher
from eventyay.plugins.badges.utils import (
    BADGE_HIDDEN_FIELDS_KEY,
    get_badge_bundle_option_choices,
    get_badge_config_position,
    get_badge_hidden_fields,
    position_has_printable_badge,
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


@receiver(layout_text_variables, dispatch_uid='badges_layout_text_variables_vouchers')
def badges_layout_text_variables_vouchers(sender, **kwargs):
    def voucher_value(field):
        return lambda op, order, event: getattr(op.voucher, field, '') if op.voucher_id else ''

    return {
        'voucher_code': {
            'label': _('Voucher code'),
            'editor_sample': 'SAMPLE123',
            'evaluate': voucher_value('code'),
        },
        'voucher_tag': {
            'label': _('Voucher tag'),
            'editor_sample': _('Sample tag'),
            'evaluate': voucher_value('tag'),
        },
    }


@receiver(product_copy_data, dispatch_uid='badges_product_copy')
def copy_product(sender, source, target, **kwargs):
    try:
        inst = BadgeProduct.objects.get(product=source)
        BadgeProduct.objects.create(product=target, layout=inst.layout)
    except BadgeProduct.DoesNotExist:
        pass


@receiver(signal=event_copy_data, dispatch_uid='badges_copy_data')
def event_copy_data_receiver(sender, other, question_map, product_map, voucher_map=None, **kwargs):
    from eventyay.base.models import Question

    identifier_map = {
        old_question.identifier: question_map[old_question.pk]
        for old_question in Question.objects.filter(event=other).only('pk', 'identifier')
        if old_question.pk in question_map and old_question.identifier
    }
    layout_map = {}
    for bl in other.badge_layouts.all():
        oldid = bl.pk
        bl = copy.copy(bl)
        bl.pk = None
        bl.event = sender

        layout = json.loads(bl.layout)
        for o in layout:
            if o.get('type') in ('text', 'textarea') and o.get('content', '').startswith('question_'):
                o['content'] = remap_question_content_key(o['content'], question_map, identifier_map)
        bl.layout = json.dumps(layout)
        ask_user_fields = []
        for field in bl.ask_user_fields_data:
            if field.startswith('question_'):
                remapped = remap_question_content_key(field, question_map, identifier_map)
                if remapped != field:
                    ask_user_fields.append(remapped)
            else:
                ask_user_fields.append(field)
        bl.ask_user_fields_data = ask_user_fields
        bl.save()

        if bl.background and bl.background.name:
            bl.background.save('background.pdf', bl.background)

        layout_map[oldid] = bl

    for bi in BadgeProduct.objects.filter(product__event=other):
        BadgeProduct.objects.create(product=product_map.get(bi.product_id), layout=layout_map.get(bi.layout_id))

    if voucher_map:
        for bv in BadgeVoucher.objects.filter(voucher__event=other):
            mapped_voucher = voucher_map.get(bv.voucher_id)
            if mapped_voucher:
                BadgeVoucher.objects.create(voucher=mapped_voucher, layout=layout_map.get(bv.layout_id))


@receiver(question_form_fields, dispatch_uid='badges_question_form_fields')
def badge_question_form_fields(sender, position, **kwargs):
    if get_badge_config_position(position) != position:
        return {}

    choices = get_badge_bundle_option_choices(sender, position)
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


@receiver(order_position_buttons, dispatch_uid='badges_control_order_buttons')
def control_order_position_info(sender: Event, position, request, order: Order, **kwargs):
    if not position_has_printable_badge(sender, position):
        return ''
    template = get_template('pretixplugins/badges/control_order_position_buttons.html')
    ctx = {'order': order, 'request': request, 'event': sender, 'position': position}
    return template.render(ctx, request=request).strip()


@receiver(order_info, dispatch_uid='badges_control_order_info')
def control_order_info(sender: Event, request, order: Order, **kwargs):
    if not any(position_has_printable_badge(sender, p) for p in order.positions.all()):
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
