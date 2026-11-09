from django.conf import settings
from django.urls import resolve

from eventyay.common.context_processors import main_site_route_exists


def test_main_site_route_exists_ignores_organizer_catch_all():
    assert main_site_route_exists('/terms') is True
    assert main_site_route_exists('/no-such-platform-page') is False
    assert main_site_route_exists('https://docs.eventyay.com') is True


def test_custom_domains_redirect_pricing_to_main_site():
    for urlconf in (
        'eventyay.multidomain.organizer_domain_urlconf',
        'eventyay.multidomain.event_domain_urlconf',
    ):
        match = resolve('/pricing/', urlconf=urlconf)

        assert match.url_name == 'page.pricing'
        assert match.func.view_initkwargs['url'] == f'{settings.SITE_URL.rstrip("/")}/pricing/'
