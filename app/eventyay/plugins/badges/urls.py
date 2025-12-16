from django.urls import path

from eventyay.api.urls import event_router
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)
from eventyay.plugins.badges.api import (
    BadgeDownloadView,
    BadgeLayoutViewSet,
    BadgePreviewView,
    BadgeProductViewSet,
)

from .views import (
    LayoutCreate,
    LayoutDelete,
    LayoutEditorView,
    LayoutListView,
    LayoutSetDefault,
    OrderPrintDo,
)

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/',
        LayoutListView.as_view(),
        name='index',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/print',
        OrderPrintDo.as_view(),
        name='print',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/add',
        LayoutCreate.as_view(),
        name='add',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/default',
        LayoutSetDefault.as_view(),
        name='default',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/delete',
        LayoutDelete.as_view(),
        name='delete',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/badges/<int:layout>/editor',
        LayoutEditorView.as_view(),
        name='edit',
    ),
    path(
        'api/v1/organizers/<orgslug:organizer>/events/<slug:event>/orderpositions/<int:position>/download/badge/',
        BadgeDownloadView.as_view(),
        name='api-badge-download',
    ),
    path(
        'api/v1/organizers/<orgslug:organizer>/events/<slug:event>/orderpositions/<int:position>/preview/badge/',
        BadgePreviewView.as_view(),
        name='badge-preview',
    ),
]

event_router.register('badgelayouts', BadgeLayoutViewSet)
event_router.register('badgeitems', BadgeProductViewSet)
