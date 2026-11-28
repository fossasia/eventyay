from django.urls import path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401

from .views import (
    MarketplaceBuyView,
    MarketplaceView,
    ResaleAdminWithdrawView,
    ResaleOverviewView,
    ResaleSellView,
    ResaleSettingsView,
    ResaleWithdrawView,
)


urlpatterns = [
    path(
        'control/event/<orgslug:organizer>/<slug:event>/resale/',
        ResaleOverviewView.as_view(),
        name='overview',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/resale/settings',
        ResaleSettingsView.as_view(),
        name='settings',
    ),
    path(
        'control/event/<orgslug:organizer>/<slug:event>/resale/<int:listing>/withdraw',
        ResaleAdminWithdrawView.as_view(),
        name='admin_withdraw',
    ),
]

event_patterns = [
    path('resale/', MarketplaceView.as_view(), name='marketplace'),
    path('resale/buy/<int:listing>/', MarketplaceBuyView.as_view(), name='buy'),
    path(
        'order/<str:order>/<str:secret>/resale/sell/<int:position>/',
        ResaleSellView.as_view(),
        name='sell',
    ),
    path(
        'order/<str:order>/<str:secret>/resale/withdraw/<int:listing>/',
        ResaleWithdrawView.as_view(),
        name='withdraw',
    ),
]
