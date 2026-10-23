from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import RequestFactory
from django.utils.html import format_html

from eventyay.common.signals import user_dashboard_links


def shifts_link(sender, **kwargs):
    return format_html(
        '<a class="dropdown-item" href="/common/my-shifts/"><i class="fa fa-calendar-check-o"></i> {}</a>', 'My shifts'
    )


def exhibitions_link(sender, **kwargs):
    return format_html(
        '<a class="dropdown-item" href="/common/exhibitions/"><i class="fa fa-building-o"></i> {}</a>', 'My exhibitions'
    )


def no_link(sender, **kwargs):
    return ''


def test_sorted_signal_orders_dashboard_links_like_sidebar():
    # Connected in reverse order, as happens when the plugin providing "My shifts" loads first.
    user_dashboard_links.connect(shifts_link, dispatch_uid='test_shifts_link')
    user_dashboard_links.connect(no_link, dispatch_uid='test_no_link')
    user_dashboard_links.connect(exhibitions_link, dispatch_uid='test_exhibitions_link')
    try:
        request = RequestFactory().get('/common/')
        # Installed plugins answer this signal too; an anonymous user makes them return nothing.
        request.user = AnonymousUser()
        html = Template(
            '{% load eventsignal %}{% sorted_signal "eventyay.common.signals.user_dashboard_links" request %}'
        ).render(Context({'request': request}))
    finally:
        for uid in ('test_shifts_link', 'test_no_link', 'test_exhibitions_link'):
            user_dashboard_links.disconnect(dispatch_uid=uid)

    assert html.index('My exhibitions') < html.index('My shifts')
    assert '&lt;a' not in html
