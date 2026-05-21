from django.db.models import Q

from eventyay.base.models import Event


def get_startpage_events_queryset(*, search_query: str = ''):
    """
    Shared queryset for platform start page listings and related consumers (e.g. CSP).
    """
    qs = (
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects')
        .filter(live=True, is_public=True)
        .exclude(display_settings__exclude_from_start_page=True)
    )
    if search_query:
        qs = qs.filter(name__icontains=search_query).exclude(display_settings__exclude_from_search=True)
    else:
        qs = qs.filter(Q(startpage_visible=True) | Q(startpage_featured=True))
    return qs.order_by('date_from')
