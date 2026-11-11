from django.db import models
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scopes_disabled

from eventyay.base.models.mixins import PretalxModel
from eventyay.base.models.vouchers import Voucher


class SpeakerVoucherStatus(models.TextChoices):
    NOT_SENT = 'not_sent', _('Not sent')
    SENT = 'sent', _('Sent — not claimed')
    CLAIMED = 'claimed', _('Claimed')


def usable_batch_vouchers(event, voucher_tag: str):
    """Unused, unexpired vouchers in the given batch that are not yet assigned.

    Codes reserved in an active cart are excluded, matching RedeemView /
    CartManager availability so we never email a code that redemption would reject.
    """
    if not voucher_tag:
        return Voucher.objects.none()

    from eventyay.base.models.orders import CartPosition

    active_cart_reservations = (
        CartPosition.objects.filter(
            voucher_id=OuterRef('pk'),
            event=event,
            expires__gte=now(),
        )
        .order_by()
        .values('voucher_id')
        .annotate(c=Count('id'))
        .values('c')
    )
    return (
        Voucher.objects.filter(
            event=event,
            tag=voucher_tag,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now()))
        .filter(speaker_voucher_link__isnull=True)
        .annotate(
            cart_reserved=Coalesce(
                Subquery(active_cart_reservations, output_field=IntegerField()),
                0,
            )
        )
        .filter(redeemed__lt=F('max_usages') - F('cart_reserved'))
    )


class SpeakerVoucherSettings(PretalxModel):
    event = models.OneToOneField(
        to='Event',
        on_delete=models.CASCADE,
        related_name='speaker_voucher_settings',
    )
    enabled = models.BooleanField(
        default=False,
        verbose_name=_('Enable speaker vouchers'),
        help_text=_('Allow sending ticket vouchers to speakers with confirmed sessions.'),
    )
    voucher_tag = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Voucher batch (tag)'),
        help_text=_('The tag that identifies the voucher batch in Tickets → Vouchers.'),
    )

    class Meta:
        verbose_name = _('Speaker voucher settings')
        verbose_name_plural = _('Speaker voucher settings')

    def __str__(self):
        return f'Speaker voucher settings for {self.event.slug}'

    def get_available_vouchers(self):
        if not self.voucher_tag:
            return Voucher.objects.none()
        with scopes_disabled():
            return usable_batch_vouchers(self.event, self.voucher_tag)

    def batch_total_count(self) -> int:
        if not self.voucher_tag:
            return 0
        with scopes_disabled():
            return Voucher.objects.filter(event=self.event, tag=self.voucher_tag).count()

    def batch_remaining_count(self) -> int:
        return self.get_available_vouchers().count()


class SpeakerVoucher(PretalxModel):
    event = models.ForeignKey(
        to='Event',
        on_delete=models.CASCADE,
        related_name='speaker_vouchers',
    )
    # Kept (with speaker_profile=NULL) when the profile is deleted, so a code that
    # was already emailed is never handed to another speaker.
    speaker_profile = models.OneToOneField(
        to='SpeakerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_assignment',
    )
    voucher = models.OneToOneField(
        to='Voucher',
        on_delete=models.CASCADE,
        related_name='speaker_voucher_link',
    )
    status = models.CharField(
        max_length=20,
        choices=SpeakerVoucherStatus.choices,
        default=SpeakerVoucherStatus.NOT_SENT,
        verbose_name=_('Voucher status'),
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Sent at'),
    )

    log_prefix = 'eventyay.speaker.voucher'

    class Meta:
        verbose_name = _('Speaker voucher')
        verbose_name_plural = _('Speaker vouchers')

    def __str__(self):
        if self.speaker_profile is None or self.speaker_profile.user is None:
            return f'(deleted speaker) → {self.voucher.code}'
        return f'{self.speaker_profile.user.email} → {self.voucher.code}'

    def refresh_claimed_status(self) -> bool:
        if self.status == SpeakerVoucherStatus.CLAIMED:
            return False
        self.voucher.refresh_from_db(fields=['redeemed'])
        if self.voucher.redeemed > 0:
            self.status = SpeakerVoucherStatus.CLAIMED
            self.save(update_fields=['status'])
            return True
        return False
