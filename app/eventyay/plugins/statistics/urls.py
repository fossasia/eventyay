from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from . import views

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/statistics/',
        views.IndexView.as_view(),
        name='index',
    ),
]
