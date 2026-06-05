from collections import defaultdict
from datetime import date, datetime, time, timedelta

import dateutil.parser
from django.db.models import Q
from django.utils.timezone import make_aware


def parse_date_input(value):
    if isinstance(value, str):
        return dateutil.parser.parse(value).date()
    if isinstance(value, date):
        return value
    return None


def build_date_filter(date_from, date_to, tz):
    date_filter = Q()
    if isinstance(date_from, date):
        start_dt = make_aware(
            datetime.combine(date_from, time(hour=0, minute=0, second=0)),
            tz,
        )
        date_filter &= Q(subevent__date_from__gte=start_dt) | Q(
            subevent__isnull=True,
            order__event__date_from__gte=start_dt,
        )
    if isinstance(date_to, date):
        end_dt = make_aware(
            datetime.combine(date_to + timedelta(days=1), time(hour=0, minute=0, second=0)),
            tz,
        )
        date_filter &= Q(subevent__date_from__lt=end_dt) | Q(
            subevent__isnull=True,
            order__event__date_from__lt=end_dt,
        )
    return date_filter


def build_multi_event_date_filter(events, date_from, date_to):
    grouped_events = defaultdict(list)
    for event in events:
        grouped_events[event.tz].append(event)

    date_filter = None
    for tz, tz_events in grouped_events.items():
        group_filter = Q(order__event__in=tz_events) & build_date_filter(date_from, date_to, tz)
        date_filter = group_filter if date_filter is None else date_filter | group_filter
    return date_filter