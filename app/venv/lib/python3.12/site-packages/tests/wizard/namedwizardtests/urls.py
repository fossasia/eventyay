from django.urls import path, re_path

from .forms import (
    CookieContactWizard, Page1, Page2, Page3, Page4, SessionContactWizard,
)


def get_named_session_wizard():
    return SessionContactWizard.as_view(
        [('form1', Page1), ('form2', Page2), ('form3', Page3), ('form4', Page4)],
        url_name='nwiz_session',
        done_step_name='nwiz_session_done'
    )


def get_named_cookie_wizard():
    return CookieContactWizard.as_view(
        [('form1', Page1), ('form2', Page2), ('form3', Page3), ('form4', Page4)],
        url_name='nwiz_cookie',
        done_step_name='nwiz_cookie_done'
    )


urlpatterns = [
    re_path(r'^nwiz_session/(?P<step>.+)/$', get_named_session_wizard(), name='nwiz_session'),
    path('nwiz_session/', get_named_session_wizard(), name='nwiz_session_start'),
    re_path(r'nwiz_cookie/(?P<step>.+)/$', get_named_cookie_wizard(), name='nwiz_cookie'),
    path('nwiz_cookie/', get_named_cookie_wizard(), name='nwiz_cookie_start'),
]
