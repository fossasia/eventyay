from django.conf import settings
from django.core.files.storage import default_storage
from django.views.generic import TemplateView
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString
from django.utils import timezone

from eventyay.base.models import Event
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.permissions import is_admin_mode_active


class StartPageView(TemplateView):
    template_name = 'pretixpresale/startpage.html'

    def _can_view_testmode_event(self, event):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_administrator', False):
            return True
        return user.has_event_permission(event.organizer, event, request=self.request)

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
        search_query = self.request.GET.get('q', '').strip()
        ctx['search_query'] = search_query
        with scopes_disabled():
            qs = Event.objects.select_related('organizer').prefetch_related('_settings_objects').filter(live=True)
            if search_query:
                qs = qs.filter(name__icontains=search_query)

            events = list(qs.order_by('date_from'))
            visible_events = [
                event
                for event in events
                if not event.has_component_testmode or self._can_view_testmode_event(event)
            ]

            if search_query:
                ctx['events'] = visible_events
                return ctx

            today = timezone.localdate()
            featured_events = []
            upcoming_events = []
            past_events = []

            for event in visible_events:
                if timezone.is_aware(event.date_to):
                    event_end_date = timezone.localtime(event.date_to).date()
                else:
                    event_end_date = event.date_to.date()
                in_future = event_end_date >= today
                if in_future and event.startpage_featured and not event.has_component_testmode:
                    featured_events.append(event)
                if in_future:
                    if (event.startpage_visible and not event.startpage_featured) or event.has_component_testmode:
                        upcoming_events.append(event)
                elif event.startpage_visible or event.has_component_testmode:
                    past_events.append(event)

            ctx['featured_events'] = featured_events
            ctx['upcoming_events'] = upcoming_events
            ctx['past_events'] = list(reversed(past_events))
        return ctx
