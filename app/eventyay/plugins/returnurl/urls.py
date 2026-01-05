from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from .views import ReturnSettings

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/returnurl/settings',
        ReturnSettings.as_view(),
        name='settings',
    ),
]
