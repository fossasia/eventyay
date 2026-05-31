from django.db.models import Q

from eventyay.base.models import Event

# Only hide events that explicitly set exclude_from_start_page to true.
# .exclude(display_settings__exclude_from_start_page=True) wrongly drops rows
# where the key is missing (SQL NULL / three-valued logic).
NOT_EXCLUDED_FROM_START_PAGE = ~Q(display_settings__contains={'exclude_from_start_page': True})


def get_startpage_events_queryset(*, search_query: str = ''):
    """
    Shared queryset for platform start page listings and related consumers (e.g. CSP).

    Without ``search_query``, only events marked ``startpage_visible`` or
    ``startpage_featured`` are returned (plus ``exclude_from_start_page`` opt-out).

    With ``search_query``, any live public event matching the name is returned unless
    it opted out via ``exclude_from_start_page`` — including events not shown on the
    default start page listing.
    """
    qs = (
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects')
        .filter(live=True, is_public=True)
        .filter(NOT_EXCLUDED_FROM_START_PAGE)
    )
    if search_query:
        qs = qs.filter(name__icontains=search_query)
    else:
        qs = qs.filter(Q(startpage_visible=True) | Q(startpage_featured=True))
    return qs.order_by('date_from')
