from collections import OrderedDict
from zoneinfo import ZoneInfo

from django import forms
from django.db.models import Prefetch
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import OrderPosition

from ..exporter import ListExporter
from ..signals import register_data_exporters


class VoucherAttendeeListExporter(ListExporter):
    identifier = 'voucherattendees'
    verbose_name = _('Attendees by voucher')

    @property
    def additional_form_fields(self):
        tags = self.event.vouchers.exclude(tag='').order_by('tag').values_list('tag', flat=True).distinct()
        return OrderedDict(
            [
                (
                    'voucher_tag',
                    forms.ChoiceField(
                        label=_('Voucher tag'),
                        required=False,
                        choices=[('', _('All vouchers'))] + [(tag, tag) for tag in tags],
                        help_text=_('Only export attendees of vouchers with this tag.'),
                    ),
                ),
                (
                    'voucher_code',
                    forms.CharField(
                        label=_('Voucher code'),
                        required=False,
                        help_text=_('Only export attendees of this specific voucher.'),
                    ),
                ),
                (
                    'include_unredeemed',
                    forms.BooleanField(
                        label=_('Include vouchers that have not been redeemed yet'),
                        required=False,
                        initial=True,
                    ),
                ),
            ]
        )

    def _voucher_status(self, voucher):
        if voucher.redeemed >= voucher.max_usages:
            return _('Redeemed')
        if voucher.valid_until and voucher.valid_until < now():
            return _('Expired')
        if voucher.redeemed > 0:
            return _('Partially redeemed')
        return _('Not redeemed')

    def iterate_list(self, form_data):
        vouchers = self.event.vouchers.all()
        if form_data.get('voucher_tag'):
            vouchers = vouchers.filter(tag=form_data['voucher_tag'])
        if form_data.get('voucher_code'):
            vouchers = vouchers.filter(code__iexact=form_data['voucher_code'].strip())
        vouchers = vouchers.prefetch_related(
            Prefetch(
                'orderposition_set',
                queryset=OrderPosition.objects.select_related('order', 'product', 'variation', 'addon_to').order_by(
                    'order__datetime', 'positionid'
                ),
                to_attr='active_positions',
            )
        ).order_by('tag', 'code')

        tz = ZoneInfo(self.event.settings.timezone)
        datetime_format = '%Y-%m-%d %H:%M:%S %Z'
        include_unredeemed = form_data.get('include_unredeemed', True)

        yield [
            _('Voucher code'),
            _('Voucher tag'),
            _('Voucher status'),
            _('Redeemed'),
            _('Maximum usages'),
            _('Valid until'),
            _('Order code'),
            _('Order status'),
            _('Order date'),
            _('Attendee name'),
            _('Attendee email'),
            _('Product'),
            _('Variation'),
        ]
        yield self.ProgressSetTotal(total=len(vouchers))

        for voucher in vouchers:
            voucher_columns = [
                voucher.code,
                voucher.tag,
                self._voucher_status(voucher),
                voucher.redeemed,
                voucher.max_usages,
                voucher.valid_until.astimezone(tz).strftime(datetime_format) if voucher.valid_until else '',
            ]
            if not voucher.active_positions:
                if include_unredeemed:
                    yield voucher_columns + [''] * 7
                continue
            for op in voucher.active_positions:
                yield voucher_columns + [
                    op.order.code,
                    op.order.get_status_display(),
                    op.order.datetime.astimezone(tz).strftime(datetime_format),
                    op.attendee_name or (op.addon_to.attendee_name if op.addon_to else '') or '',
                    op.attendee_email or (op.addon_to.attendee_email if op.addon_to else '') or op.order.email or '',
                    str(op.product),
                    str(op.variation) if op.variation else '',
                ]

    def get_filename(self):
        return f'{self.event.slug}_voucher_attendees'


@receiver(register_data_exporters, dispatch_uid='exporter_voucherattendees')
def register_voucher_attendee_exporter(sender, **kwargs):
    return VoucherAttendeeListExporter
