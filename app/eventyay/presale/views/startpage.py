from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.views.generic import TemplateView
from django_scopes import scopes_disabled
from django.utils.timezone import now
from django.db.models import Q

from i18nfield.strings import LazyI18nString
from django.utils import timezone

from eventyay.base.models import Event
from eventyay.base.settings import GlobalSettingsObject


class StartPageView(TemplateView):
    template_name = 'pretixpresale/startpage.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
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
        with scopes_disabled():
            ctx['events'] = (
                Event.objects
                .select_related('organizer')
                .visible_on_startpage()
                .order_by('date_from')
            )
        return ctx
            qs = Event.objects.select_related('organizer').filter(live=True)
            today = timezone.localdate()
            ctx['featured_events'] = (
                qs.filter(startpage_featured=True, testmode=False, date_to__date__gte=today)
                .order_by('date_from')
            )
            ctx['upcoming_events'] = (
                qs.filter(startpage_visible=True, date_to__date__gte=today)
                .filter(models.Q(startpage_featured=False) | models.Q(testmode=True))
                .order_by('date_from')
            )
            ctx['past_events'] = (
                qs.filter(startpage_visible=True, date_to__date__lt=today)
                .order_by('-date_from')
            )
        return ctx
