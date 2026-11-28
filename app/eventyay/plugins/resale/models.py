from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import LoggedModel


class ResaleListing(LoggedModel):
    """A single ticket offered for resale on the public marketplace."""

    STATUS_AVAILABLE = 'available'
    STATUS_RESERVED = 'reserved'
    STATUS_SOLD = 'sold'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = (
        (STATUS_AVAILABLE, _('Available')),
        (STATUS_RESERVED, _('Reserved')),
        (STATUS_SOLD, _('Sold')),
        (STATUS_WITHDRAWN, _('Withdrawn')),
        (STATUS_EXPIRED, _('Expired')),
    )

    REFUND_NONE = 'none'
    REFUND_PENDING = 'pending'
    REFUND_DONE = 'done'
    REFUND_FAILED = 'failed'
    REFUND_CHOICES = (
        (REFUND_NONE, _('No refund')),
        (REFUND_PENDING, _('Pending')),
        (REFUND_DONE, _('Completed')),
        (REFUND_FAILED, _('Failed')),
    )

    event = models.ForeignKey(
        'base.Event',
        on_delete=models.CASCADE,
        related_name='resale_listings',
    )
    position = models.OneToOneField(
        'base.OrderPosition',
        on_delete=models.CASCADE,
        related_name='resale_listing',
    )
    seller_order = models.ForeignKey(
        'base.Order',
        on_delete=models.CASCADE,
        related_name='resale_listings_as_seller',
    )
    price = models.DecimalField(
        max_digits=13,
        decimal_places=2,
        verbose_name=_('Resale price'),
    )
    original_price = models.DecimalField(
        max_digits=13,
        decimal_places=2,
        verbose_name=_('Original purchase price'),
    )
    fee_amount = models.DecimalField(
        max_digits=13,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Processing fee'),
    )
    seller_payout = models.DecimalField(
        max_digits=13,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Seller payout'),
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
        db_index=True,
    )
    reserved_until = models.DateTimeField(null=True, blank=True)
    reserved_session = models.CharField(max_length=255, blank=True, default='')
    buyer_order = models.ForeignKey(
        'base.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resale_listings_as_buyer',
    )
    buyer_position = models.ForeignKey(
        'base.OrderPosition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resale_acquired_from',
    )
    refund_status = models.CharField(
        max_length=16,
        choices=REFUND_CHOICES,
        default=REFUND_NONE,
    )
    refund = models.ForeignKey(
        'base.OrderRefund',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resale_listings',
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    sold_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['event', 'status']),
        ]

    def __str__(self):
        return f'ResaleListing({self.pk}, {self.status}, {self.price})'

    @property
    def is_active(self) -> bool:
        return self.status in (self.STATUS_AVAILABLE, self.STATUS_RESERVED)
