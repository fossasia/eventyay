from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.test import RequestFactory, override_settings

from eventyay.base.models import Organizer
from eventyay.multidomain.urlreverse import eventreverse


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
def test_common_organizer_base_header_shows_public_profile_link():
    organizer = Organizer(name='Test Organizer', slug='testorg')
    request = RequestFactory().get('/common/organizer/testorg/')
    request.organizer = organizer
    request.user = AnonymousUser()
    request.LANGUAGE_CODE = 'en'

    template = Template(
        '{% extends "eventyay_common/base.html" %}'
        '{% block content %}<div id="test-main-body">Organiser Content</div>{% endblock %}'
    )
    rendered = template.render(Context({'request': request}))

    assert 'Public profile' in rendered
    assert f'href="{eventreverse(organizer, "presale:organizer.index")}"' in rendered
    assert 'target="_blank" rel="noopener noreferrer"' in rendered

    soup = BeautifulSoup(rendered, 'html.parser')
    main_el = soup.find('main', id='main-content')
    assert main_el is not None
    assert main_el.find(id='test-main-body') is not None
