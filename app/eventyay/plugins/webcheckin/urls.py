from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

from .views import IndexView

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/webcheckin/',
        IndexView.as_view(),
        name='index',
    ),
]
