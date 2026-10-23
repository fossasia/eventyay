import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.utils.html import format_html

from eventyay.base.templatetags.eventsignal import visible_text
from eventyay.common.signals import user_dashboard_links


def link(label, extra=''):
    def receiver(sender, **kwargs):
        return format_html('<a class="dropdown-item" href="#"><i class="fa fa-link"></i> {}{}</a>', extra, label)

    return receiver


def render_dropdown(*receivers):
    for index, receiver in enumerate(receivers):
        user_dashboard_links.connect(receiver, dispatch_uid=f'test_dropdown_link_{index}')
    try:
        request = RequestFactory().get('/common/')
        # Installed plugins answer this signal too; an anonymous user makes them return nothing.
        request.user = AnonymousUser()
        return render_to_string('common/fragment_profile_dropdown.html', {'request': request, 'base_path': ''})
    finally:
        for index in range(len(receivers)):
            user_dashboard_links.disconnect(dispatch_uid=f'test_dropdown_link_{index}')


def test_profile_dropdown_orders_plugin_links_like_sidebar():
    # Connected in reverse order, as happens when the plugin with the later label loads first.
    html = render_dropdown(link('My zines'), lambda sender, **kwargs: '', link('My albums'))

    assert html.index('My events') < html.index('My albums') < html.index('My zines') < html.index('Organizers')
    assert '&lt;a' not in html


@pytest.mark.parametrize(
    'html,expected',
    (
        ('<a href="#"><i class="fa fa-link"></i> My   shifts</a>', 'My shifts'),
        ('<a href="#">Me &lt;3</a>', 'Me <3'),
        ('<a href="#"><span class="sr-only">Open </span>Zebra<br>talks</a>', 'Zebra talks'),
        ('<a href="#"><span aria-hidden="true">*</span>Alpha</a>', 'Alpha'),
    ),
)
def test_visible_text(html, expected):
    assert visible_text(html) == expected


def test_profile_dropdown_sorts_by_decoded_visible_label():
    # Escaped, "Me <3" would sort before "Me 9" ("&" < "9"); decoded it sorts after (">" > "9").
    # The hidden "Aaa" prefix must not move "Zebra" to the top either.
    html = render_dropdown(
        link('Me <3'),
        link('Zebra', format_html('<span class="sr-only">{}</span>', 'Aaa ')),
        link('Me 9'),
    )

    assert html.index('Me 9') < html.index('Me &lt;3') < html.index('Zebra')
