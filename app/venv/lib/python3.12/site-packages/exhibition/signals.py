from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from eventyay.control.signals import nav_event, nav_event_settings


@receiver(nav_event, dispatch_uid="exhibitors_nav")
def control_nav_import(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    return [
        {
            'label': _('Exhibitors'),
            'url': reverse(
                'plugins:exhibition:info',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                }
            ),
            'active': url.namespace == 'plugins:exhibition' and url.url_name != 'settings',
            'icon': 'map-pin',
        }
    ]


@receiver(nav_event_settings, dispatch_uid='exhibitors_nav')
def navbar_info(sender, request, **kwargs):
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
        request.organizer, request.event, 'can_change_event_settings', request=request
    ):
        return []
    return [{
        'label': 'Exhibitors',
        'url': reverse(
            'plugins:exhibition:settings',
            kwargs={
                'event': request.event.slug,
                'organizer': request.organizer.slug,
            }
        ),
        'active': url.namespace == 'plugins:exhibitors' and url.url_name == 'settings',
    }]
