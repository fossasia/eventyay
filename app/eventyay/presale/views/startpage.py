from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.models import Event, OrganizerFollower
from eventyay.base.models.page import Page
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.permissions import is_admin_mode_active
from eventyay.eventyay_common.navigation import get_global_navigation
from eventyay.multidomain.urlreverse import eventreverse

_SEARCH_PAGE_LIMIT = 200


def _event_search_qs(query):
    return (
        Event.objects.select_related('organizer')
        .prefetch_related('_settings_objects')
        .filter(live=True, is_public=True, testmode=False)
        .filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(organizer__name__icontains=query)
            | Q(location__icontains=query)
        )
        .order_by('date_from')
    )


def _search_events(query, limit=10):
    with scopes_disabled():
        results = []
        for event in _event_search_qs(query)[:limit]:
            if event.has_component_testmode:
                continue
            url = eventreverse(event, 'presale:event.index')
            results.append({
                'name': str(event.name),
                'url': url,
                'date': event.get_date_range_display(),
                'image': event.visible_logo_url or event.visible_header_image_url or '',
            })
    return results


class StartPageView(TemplateView):
    template_name = 'pretixpresale/startpage.html'

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'json':
            query = request.GET.get('q', '').strip()
            if not query:
                return JsonResponse({'results': []})
            return JsonResponse({'results': _search_events(query)})
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['staff_session'] = is_admin_mode_active(self.request)
        settings_obj = GlobalSettingsObject().settings
        header_image = settings_obj.get('startpage_header_image', as_type=str, default='')
        if header_image.startswith('file://'):
            header_image = header_image[7:]
        elif header_image.startswith('public:'):
            header_image = header_image[7:]
        ctx['startpage_header_image_url'] = default_storage.url(header_image) if header_image else ''
        header_text = settings_obj.get(
            'startpage_header_text',
            as_type=LazyI18nString,
            default='',
        )
        ctx['site_name'] = settings.INSTANCE_NAME
        ctx['startpage_header_text'] = header_text or settings.INSTANCE_NAME
        if self.request.user.is_authenticated:
            ctx['nav_items'] = get_global_navigation(self.request)
        else:
            ctx['nav_items'] = []
        ctx['show_link_in_header_for_start_page'] = Page.objects.filter(
            link_on_website_start_page=True,
            link_in_header=True,
        )
        ctx['show_link_in_footer_for_start_page'] = Page.objects.filter(
            link_on_website_start_page=True,
            link_in_footer=True,
        )
        search_query = self.request.GET.get('q', '').strip()
        ctx['search_query'] = search_query
        with scopes_disabled():
            if search_query:
                qs = _event_search_qs(search_query)[:_SEARCH_PAGE_LIMIT]
                ctx['events'] = [e for e in qs if not e.has_component_testmode]
                return ctx

            qs = Event.objects.select_related('organizer').prefetch_related('_settings_objects').filter(live=True)
            qs = qs.filter(Q(startpage_visible=True) | Q(startpage_featured=True))
            events = list(qs.order_by('date_from'))
            visible_events = [event for event in events if not event.has_component_testmode]

            today = timezone.localdate()
            featured_events = []
            upcoming_events = []
            past_events = []

            for event in visible_events:
                event_end = event.date_to or event.date_from
                if timezone.is_aware(event_end):
                    event_end_date = timezone.localtime(event_end).date()
                else:
                    event_end_date = event_end.date()
                in_future = event_end_date >= today
                if in_future and event.startpage_featured:
                    featured_events.append(event)
                if in_future:
                    if event.startpage_visible and not event.startpage_featured:
                        upcoming_events.append(event)
                elif event.startpage_visible:
                    past_events.append(event)

            ctx['featured_events'] = featured_events
            ctx['upcoming_events'] = upcoming_events
            ctx['past_events'] = list(reversed(past_events))

            followed_upcoming_events = []
            if self.request.user.is_authenticated:
                followed_org_ids = OrganizerFollower.objects.filter(
                    user=self.request.user
                ).values_list('organizer_id', flat=True)
                qs = (
                    Event.objects.filter(
                        organizer_id__in=followed_org_ids,
                        live=True,
                    )
                    .filter(Q(startpage_visible=True) | Q(startpage_featured=True))
                    .filter(Q(date_to__gte=today) | Q(date_to__isnull=True, date_from__gte=today))
                    .select_related('organizer')
                    .prefetch_related('_settings_objects')
                    .order_by('date_from')[:20]
                )
                followed_upcoming_events = [e for e in qs if not e.has_component_testmode]

            ctx['followed_upcoming_events'] = followed_upcoming_events
        return ctx
