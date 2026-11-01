import re

from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings

JQUERY_SRC = re.compile(r'jquery/js/jquery-(\d+)\.(\d+)\.(\d+)\.min\.js')


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
        'redis': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        },
    },
    COMPRESS_ENABLED=False,
    HAS_REDIS=False,
)
def test_common_base_template_loads_only_jquery_3_7_1() -> None:
    request = RequestFactory().get('/common/')
    request.user = AnonymousUser()
    request.LANGUAGE_CODE = 'en'

    rendered = render_to_string('eventyay_common/base.html', {'request': request})

    versions = [tuple(int(part) for part in match) for match in JQUERY_SRC.findall(rendered)]
    assert versions == [(3, 7, 1)]


def test_vulnerable_jquery_assets_are_not_shipped() -> None:
    assert finders.find('jquery/js/jquery-3.7.1.min.js')
    assert finders.find('jquery/js/jquery-2.1.1.min.js') is None
    assert finders.find('control/jquery-3.6.0.js') is None
