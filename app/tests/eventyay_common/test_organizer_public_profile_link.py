from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
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

    rendered = render_to_string('eventyay_common/base.html', {'request': request})

    assert 'Public profile' in rendered
    assert f'href="{eventreverse(organizer, "presale:organizer.index")}"' in rendered
