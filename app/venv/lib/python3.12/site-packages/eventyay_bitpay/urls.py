from django.urls import include, path, re_path
from eventyay.multidomain import event_url

from .views import ReturnView, auth_disconnect, auth_start, redirect_view, webhook

event_patterns = [
    path(
        "bitpay/",
        include(
            [
                event_url(r"^webhook/$", webhook, name="webhook", require_live=False),
                event_url(
                    r"^redirect/$", redirect_view, name="redirect", require_live=False
                ),
                path(
                    "return/<str:order>/<str:hash>/<str:payment>/",
                    ReturnView.as_view(),
                    name="return",
                ),
            ]
        ),
    ),
]
urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/bitpay/connect/",
        auth_start,
        name="auth.start",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/bitpay/disconnect/",
        auth_disconnect,
        name="auth.disconnect",
    ),
]
