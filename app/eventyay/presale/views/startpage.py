from django.conf import settings
from django.core.files.storage import default_storage
from django.views.generic import TemplateView
from django_scopes import scopes_disabled
from django.utils.timezone import now
from django.db.models import Q

from i18nfield.strings import LazyI18nString

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
            current_time = now()

            ctx['events'] = (
                Event.objects.select_related('organizer')
                .filter(
                    live=True,
                    date_to__gte=current_time  # Exclude past events
                )
                .filter(
                    (
                        # Tickets live
                        Q(
                            tickets_published=True
                        ) &
                        (
                            Q(presale_start__isnull=True) |
                            Q(presale_start__lte=current_time)
                        ) &
                        (
                            Q(presale_end__isnull=True) |
                            Q(presale_end__gte=current_time)
                        )
                    )
                    |
                    # OR Talks live
                    Q(talks_published=True)
                )
                .order_by('date_from')
            )
        return ctx
