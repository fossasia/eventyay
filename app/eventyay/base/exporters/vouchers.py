from collections import OrderedDict, defaultdict
from collections.abc import Iterator
from zoneinfo import ZoneInfo

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope
from pydantic import BaseModel, ValidationError

from eventyay.base.exporter import ListExporter
from eventyay.base.models import LogEntry, Order, OrderPosition, Voucher
from eventyay.base.signals import register_data_exporters


# Legacy action type kept for log entries written before the rename.
VOUCHER_SENT_ACTIONS = ('eventyay.voucher.sent', 'pretix.voucher.sent')


class VoucherRecipient(BaseModel):
    recipient: str
    name: str | None = None


def get_position_product(position: OrderPosition) -> str:
    if position.variation:
        return f'{position.product} – {position.variation}'
    return str(position.product)


class VoucherAttendeeListExporter(ListExporter):
    identifier = 'voucherattendees'
    verbose_name = _('Voucher attendees')

    status_choices = (
        ('', _('All vouchers')),
        ('redeemed', _('Redeemed')),
        ('unredeemed', _('Not redeemed')),
    )

    @property
    def additional_form_fields(self) -> dict:
        with scope(organizer=self.event.organizer, event=self.event):
            tags = list(
                self.event.vouchers.filter(waitinglistentries__isnull=True)
                .exclude(tag='')
                .order_by('tag')
                .values_list('tag', flat=True)
                .distinct()
            )
        return OrderedDict(
            [
                (
                    'tag',
                    forms.ChoiceField(
                        label=_('Voucher tag'),
                        choices=[('', _('All tags')), *((tag, tag) for tag in tags)],
                        required=False,
                        help_text=_('Only include vouchers of this group.'),
                    ),
                ),
                (
                    'code',
                    forms.CharField(
                        label=_('Voucher code'),
                        required=False,
                        help_text=_('Only include the voucher with this code.'),
                    ),
                ),
                (
                    'status',
                    forms.ChoiceField(
                        label=_('Status'),
                        choices=self.status_choices,
                        required=False,
                    ),
                ),
            ]
        )

    def get_recipients(self) -> dict[int, list[VoucherRecipient]]:
        recipients = defaultdict(list)
        entries = LogEntry.objects.filter(
            event=self.event,
            content_type=ContentType.objects.get_for_model(Voucher),
            action_type__in=VOUCHER_SENT_ACTIONS,
        ).order_by('datetime')
        for entry in entries:
            try:
                recipients[entry.object_id].append(VoucherRecipient.model_validate_json(entry.data))
            except ValidationError:
                continue
        return recipients

    def iterate_list(self, form_data: dict) -> Iterator[list]:
        with scope(organizer=self.event.organizer, event=self.event):
            vouchers = self.event.vouchers.filter(waitinglistentries__isnull=True)
            if form_data.get('tag'):
                vouchers = vouchers.filter(tag=form_data['tag'])
            if code := (form_data.get('code') or '').strip():
                vouchers = vouchers.filter(code__iexact=code)
            vouchers = vouchers.order_by('tag', 'code')

            positions = defaultdict(list)
            for position in (
                OrderPosition.objects.filter(
                    voucher__in=vouchers,
                    order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING),
                )
                .select_related('order__event', 'product', 'variation', 'addon_to')
                .order_by('order__datetime', 'positionid')
            ):
                positions[position.voucher_id].append(position)

            recipients = self.get_recipients()
            status = form_data.get('status')
            tz = ZoneInfo(self.event.settings.timezone)
            current_time = now()

            yield [
                _('Voucher code'),
                _('Voucher tag'),
                _('Status'),
                _('Attendee name'),
                _('Attendee email'),
                _('Order code'),
                _('Order status'),
                _('Order date'),
                _('Product'),
            ]

            for voucher in vouchers:
                if voucher_positions := positions.get(voucher.pk):
                    if status == 'unredeemed':
                        continue
                    for position in voucher_positions:
                        order = position.order
                        yield [
                            voucher.code,
                            voucher.tag,
                            _('Redeemed'),
                            position.attendee_name
                            or (position.addon_to.attendee_name if position.addon_to else '')
                            or '',
                            position.attendee_email
                            or (position.addon_to.attendee_email if position.addon_to else '')
                            or order.email
                            or '',
                            order.code,
                            order.get_status_display(),
                            f'{order.datetime.astimezone(tz):%Y-%m-%d %H:%M:%S %Z}',
                            get_position_product(position),
                        ]
                    continue

                if status == 'redeemed':
                    continue
                voucher_recipients = recipients.get(voucher.pk)
                if voucher.valid_until and voucher.valid_until < current_time:
                    label = _('Expired')
                elif voucher_recipients:
                    label = _('Sent')
                else:
                    label = _('Not redeemed')
                for recipient in voucher_recipients or [None]:
                    yield [
                        voucher.code,
                        voucher.tag,
                        label,
                        (recipient.name or '') if recipient else '',
                        recipient.recipient if recipient else '',
                        '',
                        '',
                        '',
                        '',
                    ]

    def get_filename(self) -> str:
        return f'{self.event.slug}_voucher_attendees'


@receiver(register_data_exporters, dispatch_uid='exporter_voucherattendees')
def register_voucherattendees_exporter(sender, **kwargs):
    return VoucherAttendeeListExporter
