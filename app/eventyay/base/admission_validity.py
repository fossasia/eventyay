from datetime import timedelta

from django.utils.formats import date_format

from eventyay.base.models.product import Product


def _variation_overrides_product(variation):
    if variation is None:
        return False
    return bool(
        variation.admission_validity_mode
        or variation.admission_valid_from
        or variation.admission_valid_until
        or variation.admission_valid_from_offset_minutes is not None
        or variation.admission_valid_until_offset_minutes is not None
    )


def _catalog_source(product, variation=None):
    if _variation_overrides_product(variation):
        return variation
    return product


def _effective_mode(source):
    mode = source.admission_validity_mode or ''
    if not mode and (source.admission_valid_from or source.admission_valid_until):
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
    valid_from = window_start
    if offset_from is not None:
        valid_from = window_start + timedelta(minutes=offset_from)
    if offset_until is not None:
        valid_until = window_start + timedelta(minutes=offset_until)
    elif window_end:
        valid_until = window_end
    else:
        valid_until = None
    return valid_from, valid_until


def resolve_catalog_admission_bounds(product, variation=None, event=None, subevent=None):
    """
    Resolve the configured check-in window from product catalog data.

    Variation settings override the product when any admission validity field is set
    on the variation. Fixed windows use explicit datetimes; subevent/event modes derive
    bounds from the assigned date or whole event, optionally shifted by minute offsets.
    """
    source = _catalog_source(product, variation)
    mode = _effective_mode(source)
    if mode in ('', Product.ADMISSION_VALIDITY_MODE_NONE):
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


def assign_issued_admission_bounds(position):
    """
    Copy the resolved check-in window onto an order position at purchase time.

    The stored values define check-in enforcement for this ticket even if the
    product is edited later.
    """
    valid_from, valid_until = resolve_catalog_admission_bounds(
        position.product,
        position.variation,
        event=position.order.event,
        subevent=position.subevent,
    )
    position.admission_valid_from = valid_from
    position.admission_valid_until = valid_until


def get_issued_admission_bounds(position):
    """Effective check-in window for a sold ticket (purchase-time snapshot)."""
    return position.admission_valid_from, position.admission_valid_until


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


def format_catalog_admission_validity(product, event, subevent=None, variation=None, *, fallback_to_event=False):
    valid_from, valid_until = resolve_catalog_admission_bounds(
        product, variation=variation, event=event, subevent=subevent
    )
    if valid_from or valid_until:
        return format_admission_window(valid_from, valid_until, event.tz)
    if not fallback_to_event:
        return ''
    source = subevent or event
    return format_admission_window(source.date_from, source.date_to, event.tz)


def format_issued_admission_validity(position, event, *, fallback_to_event=False):
    valid_from, valid_until = get_issued_admission_bounds(position)
    if valid_from or valid_until:
        return format_admission_window(valid_from, valid_until, event.tz)
    if not fallback_to_event:
        return ''
    source = position.subevent or event
    return format_admission_window(source.date_from, source.date_to, event.tz)
