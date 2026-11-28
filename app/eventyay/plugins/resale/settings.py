from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.utils.translation import gettext_lazy as _

from eventyay.base.settings import settings_hierarkey


settings_hierarkey.add_default('resale_enabled', 'False', bool)
settings_hierarkey.add_default('resale_suspended', 'False', bool)
settings_hierarkey.add_default('resale_products', '[]', list)
settings_hierarkey.add_default('resale_fee_mode', 'fixed', str)
settings_hierarkey.add_default('resale_fee_fixed', '5.00', Decimal)
settings_hierarkey.add_default('resale_fee_percent', '0.00', Decimal)
settings_hierarkey.add_default('resale_available_from', None, datetime)
settings_hierarkey.add_default('resale_available_until', None, datetime)
settings_hierarkey.add_default('resale_max_price_mode', 'original', str)
settings_hierarkey.add_default('resale_reservation_minutes', '30', int)

FEE_MODE_FIXED = 'fixed'
FEE_MODE_PERCENT = 'percent'
FEE_MODE_CHOICES = (
    (FEE_MODE_FIXED, _('Fixed amount')),
    (FEE_MODE_PERCENT, _('Percentage of resale price')),
)

MAX_PRICE_ORIGINAL = 'original'
MAX_PRICE_CHOICES = (
    (MAX_PRICE_ORIGINAL, _('Original purchase price')),
)


def marketplace_is_open(event) -> bool:
    """Return whether the public marketplace is currently open for trading."""
    if 'eventyay.plugins.resale' not in event.get_plugins():
        return False
    if not event.settings.get('resale_enabled', as_type=bool):
        return False
    if event.settings.get('resale_suspended', as_type=bool):
        return False
    from django.utils.timezone import now

    now_dt = now()
    available_from = event.settings.get('resale_available_from', as_type=datetime)
    available_until = event.settings.get('resale_available_until', as_type=datetime)
    if available_from and now_dt < available_from:
        return False
    if available_until and now_dt > available_until:
        return False
    return True


def reservation_ttl(event) -> timedelta:
    minutes = int(event.settings.get('resale_reservation_minutes', as_type=int) or 30)
    return timedelta(minutes=max(1, minutes))


def eligible_product_ids(event) -> set[int]:
    raw = event.settings.get('resale_products', as_type=list) or []
    ids = set()
    for value in raw:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return ids
