from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from .views import HubSpotSettings

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/hubspot/settings',
        HubSpotSettings.as_view(),
        name='settings',
    ),
]
