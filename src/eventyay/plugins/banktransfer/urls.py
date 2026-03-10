from django.urls import path

from eventyay.api.urls import orga_router
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)
from eventyay.plugins.banktransfer.api import BankImportJobViewSet

from . import views

urlpatterns = [
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/import/',
        views.OrganizerImportView.as_view(),
        name='import',
    ),
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/job/<int:job>/',
        views.OrganizerJobDetailView.as_view(),
        name='import.job',
    ),
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/action/',
        views.OrganizerActionView.as_view(),
        name='import.action',
    ),
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/refunds/',
        views.OrganizerRefundExportListView.as_view(),
        name='refunds.list',
    ),
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/export/<int:id>/',
        views.OrganizerDownloadRefundExportView.as_view(),
        name='refunds.download',
    ),
    path(
        'control/organizer/<orgslug:organizer>/banktransfer/sepa-export/<int:id>/',
        views.OrganizerSepaXMLExportView.as_view(),
        name='refunds.sepa',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/import/',
        views.EventImportView.as_view(),
        name='import',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/job/<int:job>/',
        views.EventJobDetailView.as_view(),
        name='import.job',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/action/',
        views.EventActionView.as_view(),
        name='import.action',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/refunds/',
        views.EventRefundExportListView.as_view(),
        name='refunds.list',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/export/<int:id>/',
        views.EventDownloadRefundExportView.as_view(),
        name='refunds.download',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/banktransfer/sepa-export/<int:id>/',
        views.EventSepaXMLExportView.as_view(),
        name='refunds.sepa',
    ),
]

orga_router.register('bankimportjobs', BankImportJobViewSet)
