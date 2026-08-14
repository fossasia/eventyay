from datetime import timedelta
from types import SimpleNamespace

from django.utils.formats import date_format
from django.utils.timezone import now as timezone_now

from eventyay.base.models.product import Product, ProductVariation

ADMISSION_VALIDITY_FIELD_NAMES = (
    'admission_validity_mode',
    'admission_valid_from',
    'admission_valid_until',
    'admission_valid_from_offset_minutes',
    'admission_valid_until_offset_minutes',
)


def _pick_attr(variation, product, attr):
    value = getattr(variation, attr)
    if value is not None:
        return value
    return getattr(product, attr)


def _merged_catalog_config(product, variation=None):
    """
    Merge product and variation admission settings.

    Variation mode ``inherit`` (default) keeps the product mode and overlays only
    explicitly set variation fields. Any other variation mode replaces the product
    mode entirely. Product ``ADMISSION_VALIDITY_MODE_NONE`` is ``''``; variations
    distinguish that from inherit via the explicit ``inherit`` mode, so a variation
    can clear a product restriction by selecting "No check-in time restriction".
    """
    if variation is None:
        return product

    var_mode = variation.admission_validity_mode
    if var_mode == ProductVariation.ADMISSION_VALIDITY_MODE_INHERIT:
        mode = product.admission_validity_mode or Product.ADMISSION_VALIDITY_MODE_NONE
    else:
        # Keep '' (NONE) as an explicit override; do not treat it as "unset".
        mode = var_mode if var_mode is not None else Product.ADMISSION_VALIDITY_MODE_NONE

    if mode == Product.ADMISSION_VALIDITY_MODE_NONE:
        return SimpleNamespace(
            admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_NONE,
            admission_valid_from=None,
            admission_valid_until=None,
            admission_valid_from_offset_minutes=None,
            admission_valid_until_offset_minutes=None,
        )

    return SimpleNamespace(
        admission_validity_mode=mode,
        admission_valid_from=_pick_attr(variation, product, 'admission_valid_from'),
        admission_valid_until=_pick_attr(variation, product, 'admission_valid_until'),
        admission_valid_from_offset_minutes=_pick_attr(
            variation, product, 'admission_valid_from_offset_minutes'
        ),
        admission_valid_until_offset_minutes=_pick_attr(
            variation, product, 'admission_valid_until_offset_minutes'
        ),
    )


def _effective_mode(source):
    mode = source.admission_validity_mode or Product.ADMISSION_VALIDITY_MODE_NONE
    if mode == ProductVariation.ADMISSION_VALIDITY_MODE_INHERIT:
        return Product.ADMISSION_VALIDITY_MODE_NONE
    if mode == Product.ADMISSION_VALIDITY_MODE_NONE and (
        source.admission_valid_from or source.admission_valid_until
    ):
        return Product.ADMISSION_VALIDITY_MODE_FIXED
    return mode


def _validity_window(event, subevent, mode):
    if mode == Product.ADMISSION_VALIDITY_MODE_EVENT:
        return event.date_from, event.date_to
    if mode == Product.ADMISSION_VALIDITY_MODE_SUBEVENT:
        if subevent is None:
            return None, None
        return subevent.date_from, subevent.date_to
    return None, None


def _apply_minute_offsets(window_start, window_end, offset_from, offset_until):
    if window_start is None:
        return None, None

    valid_from = window_start + timedelta(minutes=offset_from) if offset_from is not None else window_start
    if offset_until is not None:
        valid_until = window_start + timedelta(minutes=offset_until)
    else:
        valid_until = window_end

    # Keep resolved windows inside the underlying event/date range.
    if valid_from and valid_from < window_start:
        valid_from = window_start
    if window_end and valid_until and valid_until > window_end:
        valid_until = window_end
    return valid_from, valid_until


def resolve_catalog_admission_bounds(product, variation=None, event=None, subevent=None):
    """
    Resolve the configured check-in window from product catalog data.

    Variation settings are merged field-by-field with the product. Fixed windows use
    explicit datetimes; subevent/event modes derive bounds from the assigned date or
    whole event, optionally shifted by minute offsets.
    """
    source = _merged_catalog_config(product, variation)
    mode = _effective_mode(source)
    if mode == Product.ADMISSION_VALIDITY_MODE_NONE:
        return None, None
    if mode == Product.ADMISSION_VALIDITY_MODE_FIXED:
        return source.admission_valid_from, source.admission_valid_until
    if event is None:
        return None, None
    window_start, window_end = _validity_window(event, subevent, mode)
    return _apply_minute_offsets(
        window_start,
        window_end,
        source.admission_valid_from_offset_minutes,
        source.admission_valid_until_offset_minutes,
    )


def _catalog_bounds_for_position(position):
    product = getattr(position, 'product', None)
    order = getattr(position, 'order', None)
    if product is None or order is None:
        return None, None
    return resolve_catalog_admission_bounds(
        product,
        position.variation,
        event=order.event,
        subevent=position.subevent,
    )


def assign_issued_admission_bounds(position):
    """
    Copy the resolved check-in window onto an order position at purchase time.

    When catalog bounds exist, the stored values freeze that window for the ticket.
    When both stored fields remain ``None`` (no restriction at issue time, or a
    pre-feature position), check-in falls back to the current catalog configuration.
    """
    position.admission_valid_from, position.admission_valid_until = _catalog_bounds_for_position(position)


def get_issued_admission_bounds(position):
    """
    Effective check-in window for a sold ticket.

    Prefer the purchase-time snapshot when either bound is set. If both are
    ``None`` (legacy positions or tickets issued with no restriction), fall back
    to the current product/variation catalog configuration.
    """
    valid_from = position.admission_valid_from
    valid_until = position.admission_valid_until
    if valid_from is not None or valid_until is not None:
        return valid_from, valid_until
    return _catalog_bounds_for_position(position)


def is_within_admission_bounds(valid_from, valid_until, dt):
    if valid_from and dt < valid_from:
        return False
    if valid_until and dt > valid_until:
        return False
    return True


def is_catalog_admission_currently_valid(product, variation=None, event=None, subevent=None, dt=None):
    valid_from, valid_until = resolve_catalog_admission_bounds(product, variation, event, subevent)
    if not valid_from and not valid_until:
        return True
    return is_within_admission_bounds(valid_from, valid_until, dt or timezone_now())


def is_product_catalog_admission_orderable(product, event=None, subevent=None, dt=None):
    if not product.has_variations:
        return is_catalog_admission_currently_valid(product, None, event, subevent, dt)
    return any(
        is_catalog_admission_currently_valid(product, variation, event, subevent, dt)
        for variation in product.variations.all()
        if variation.active
    )


def has_issued_admission_bounds(position):
    valid_from, valid_until = get_issued_admission_bounds(position)
    return bool(valid_from or valid_until)


def format_admission_window(valid_from, valid_until, tz=None):
    if not valid_from and not valid_until:
        return ''

    def _fmt(dt):
        if dt is None:
            return ''
        if tz is not None:
            dt = dt.astimezone(tz)
        return date_format(dt, 'SHORT_DATETIME_FORMAT')

    if valid_from and valid_until:
        return f'{_fmt(valid_from)} – {_fmt(valid_until)}'
    if valid_from:
        return _fmt(valid_from)
    return _fmt(valid_until)


def _format_bounds_or_event_fallback(valid_from, valid_until, event, fallback_source, *, fallback_to_event):
    if valid_from or valid_until:
        return format_admission_window(valid_from, valid_until, event.tz)
    if not fallback_to_event:
        return ''
    return format_admission_window(fallback_source.date_from, fallback_source.date_to, event.tz)


def format_catalog_admission_validity(product, event, subevent=None, variation=None, *, fallback_to_event=False):
    valid_from, valid_until = resolve_catalog_admission_bounds(
        product, variation=variation, event=event, subevent=subevent
    )
    return _format_bounds_or_event_fallback(
        valid_from,
        valid_until,
        event,
        subevent or event,
        fallback_to_event=fallback_to_event,
    )


def format_issued_admission_validity(position, event, *, fallback_to_event=False):
    valid_from, valid_until = get_issued_admission_bounds(position)
    return _format_bounds_or_event_fallback(
        valid_from,
        valid_until,
        event,
        position.subevent or event,
        fallback_to_event=fallback_to_event,
    )
