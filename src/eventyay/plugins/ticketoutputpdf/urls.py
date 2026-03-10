from django.urls import path

from eventyay.api.urls import event_router
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)
from eventyay.plugins.ticketoutputpdf.api import (
    TicketLayoutProductViewSet,
    TicketLayoutViewSet,
)
from eventyay.plugins.ticketoutputpdf.views import (
    LayoutCreate,
    LayoutDelete,
    LayoutEditorView,
    LayoutGetDefault,
    LayoutListView,
    LayoutSetDefault,
)

urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/',
        LayoutListView.as_view(),
        name='index',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/add',
        LayoutCreate.as_view(),
        name='add',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/<int:layout>/default',
        LayoutSetDefault.as_view(),
        name='default',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/default',
        LayoutGetDefault.as_view(),
        name='getdefault',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/<int:layout>/delete',
        LayoutDelete.as_view(),
        name='delete',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/pdfoutput/<int:layout>/editor',
        LayoutEditorView.as_view(),
        name='edit',
    ),
]
event_router.register('ticketlayouts', TicketLayoutViewSet)
event_router.register('ticketlayoutproducts', TicketLayoutProductViewSet)
