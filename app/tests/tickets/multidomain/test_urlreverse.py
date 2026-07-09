import datetime
from decimal import Decimal

import jwt
import pytest
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.eventyay_common.utils import encode_email
from eventyay.multidomain.models import KnownDomain
from eventyay.multidomain.urlreverse import (
    build_absolute_uri,
    build_join_video_url,
    eventreverse,
    generate_video_token_url,
)
from eventyay.presale.views.event import JoinOnlineVideoView
from tests.tickets import assert_num_queries


@pytest.fixture
def env():
    o = Organizer.objects.create(name='MRMCD', slug='mrmcd')
    event = Event.objects.create(organizer=o, name='MRMCD2015', slug='2015', date_from=now())
    settings.SITE_URL = 'http://example.com'
    event.get_cache().clear()
    return o, event


@pytest.mark.django_db
def test_event_main_domain_front_page(env):
    assert eventreverse(env[1], 'presale:event.index') == '/mrmcd/2015/'
    assert eventreverse(env[0], 'presale:organizer.index') == '/mrmcd/'


@pytest.mark.django_db
def test_event_custom_domain_kwargs(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    assert eventreverse(env[1], 'presale:event.checkout', {'step': 'payment'}) == 'http://barfoo/checkout/payment/'


@pytest.mark.django_db
def test_event_org_domain_kwargs(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert eventreverse(env[1], 'presale:event.checkout', {'step': 'payment'}) == 'http://foobar/2015/checkout/payment/'


@pytest.mark.django_db
def test_event_main_domain_kwargs(env):
    assert eventreverse(env[1], 'presale:event.checkout', {'step': 'payment'}) == '/mrmcd/2015/checkout/payment/'


@pytest.mark.django_db
def test_event_org_domain_front_page(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert eventreverse(env[1], 'presale:event.index') == 'http://foobar/2015/'
    assert eventreverse(env[0], 'presale:organizer.index') == 'http://foobar/'


@pytest.mark.django_db
def test_event_custom_domain_front_page(env):
    KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    assert eventreverse(env[1], 'presale:event.index') == 'http://barfoo/'
    assert eventreverse(env[0], 'presale:organizer.index') == '/mrmcd/'


@pytest.mark.django_db
def test_event_custom_and_org_domain_front_page(env):
    KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert eventreverse(env[1], 'presale:event.index') == 'http://barfoo/'
    assert eventreverse(env[0], 'presale:organizer.index') == 'http://foobar/'


@pytest.mark.django_db
def test_event_org_domain_keep_port(env):
    settings.SITE_URL = 'http://example.com:8081'
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert eventreverse(env[1], 'presale:event.index') == 'http://foobar:8081/2015/'


@pytest.mark.django_db
def test_event_org_domain_keep_scheme(env):
    settings.SITE_URL = 'https://example.com'
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert eventreverse(env[1], 'presale:event.index') == 'https://foobar/2015/'


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
)
def test_event_main_domain_cache(env):
    env[0].get_cache().clear()
    with assert_num_queries(1):
        eventreverse(env[1], 'presale:event.index')
    with assert_num_queries(0):
        eventreverse(env[1], 'presale:event.index')


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
)
def test_event_org_domain_cache(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    env[0].get_cache().clear()
    with assert_num_queries(1):
        eventreverse(env[1], 'presale:event.index')
    with assert_num_queries(0):
        eventreverse(env[1], 'presale:event.index')


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
)
def test_event_custom_domain_cache(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    env[0].get_cache().clear()
    with assert_num_queries(1):
        eventreverse(env[1], 'presale:event.index')
    with assert_num_queries(0):
        eventreverse(env[1], 'presale:event.index')


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
)
@scopes_disabled()
def test_event_org_domain_cache_clear(env):
    kd = KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    env[0].cache.clear()
    with assert_num_queries(1):
        eventreverse(env[1], 'presale:event.index')
    kd.delete()
    with assert_num_queries(2):
        ev = Event.objects.get(pk=env[1].pk)
        assert ev.pk == env[1].pk
        assert ev.organizer == env[0]
    with assert_num_queries(1):
        eventreverse(ev, 'presale:event.index')


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
)
@scopes_disabled()
def test_event_custom_domain_cache_clear(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    kd = KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    env[0].cache.clear()
    with assert_num_queries(1):
        eventreverse(env[1], 'presale:event.index')
    kd.delete()
    with assert_num_queries(2):
        ev = Event.objects.get(pk=env[1].pk)
        assert ev.pk == env[1].pk
        assert ev.organizer == env[0]
    with assert_num_queries(1):
        eventreverse(ev, 'presale:event.index')


@pytest.mark.django_db
def test_event_main_domain_absolute(env):
    assert build_absolute_uri(env[1], 'presale:event.index') == 'http://example.com/mrmcd/2015/'


@pytest.mark.django_db
def test_event_custom_domain_absolute(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    KnownDomain.objects.create(domainname='barfoo', organizer=env[0], event=env[1])
    assert build_absolute_uri(env[1], 'presale:event.index') == 'http://barfoo/'


@pytest.mark.django_db
def test_event_org_domain_absolute(env):
    KnownDomain.objects.create(domainname='foobar', organizer=env[0])
    assert build_absolute_uri(env[1], 'presale:event.index') == 'http://foobar/2015/'


@pytest.fixture
def video_event(env):
    organizer, event = env
    ticket = Product.objects.create(
        event=event,
        name='Ticket',
        default_price=Decimal('10.00'),
        admission=True,
    )
    event.settings.set('venueless_url', 'http://video.example.com/')
    event.settings.set('venueless_issuer', 'test-issuer')
    event.settings.set('venueless_audience', 'test-audience')
    event.settings.set('venueless_secret', 'test-secret')
    event.settings.set('venueless_all_products', True)
    order = Order.objects.create(
        event=event,
        email='attendee@example.com',
        status=Order.STATUS_PAID,
        total=Decimal('10.00'),
        datetime=now(),
        expires=now() + datetime.timedelta(days=1),
    )
    position = OrderPosition.objects.create(
        order=order,
        product=ticket,
        price=Decimal('10.00'),
        positionid=1,
        attendee_name_parts={'full_name': 'Jane Doe'},
    )
    return event, order, position


@pytest.mark.django_db
@scopes_disabled()
def test_build_join_video_url_matches_presale_token(video_event):
    event, order, position = video_event
    email_url = build_join_video_url(event, order)

    view = JoinOnlineVideoView()
    view.request = type('Request', (), {'event': event})()
    presale_url = view.generate_token_url(view.request, position, order)

    email_token = email_url.split('#token=')[1]
    presale_token = presale_url.split('#token=')[1]
    decode_kwargs = {
        'algorithms': ['HS256'],
        'audience': 'test-audience',
        'issuer': 'test-issuer',
    }
    email_payload = jwt.decode(email_token, 'test-secret', **decode_kwargs)
    presale_payload = jwt.decode(presale_token, 'test-secret', **decode_kwargs)

    assert email_payload['uid'] == presale_payload['uid'] == encode_email('attendee@example.com')
    assert 'attendee' in email_payload['traits']
    assert set(email_payload['traits']) == set(presale_payload['traits'])
    assert email_url.split('#')[0] == presale_url.split('#')[0]
    assert f'/{event.organizer.slug}/{event.slug}/video/' in email_url


@pytest.mark.django_db
@scopes_disabled()
def test_build_join_video_url_returns_empty_without_allowed_products(video_event):
    event, order, _position = video_event
    event.settings.set('venueless_all_products', False)
    event.settings.set('venueless_products', [])

    assert build_join_video_url(event, order) == ''


@pytest.mark.django_db
@scopes_disabled()
def test_generate_video_token_url_returns_empty_without_position(video_event):
    event, order, _position = video_event

    assert generate_video_token_url(event, encode_email(order.email), None) == ''


@pytest.mark.django_db
@scopes_disabled()
def test_generate_video_token_url_supports_legacy_token_placeholder(video_event):
    event, order, _position = video_event
    event.settings.set('venueless_url', 'http://video.example.com/join?token={token}')

    url = build_join_video_url(event, order)

    assert '#token=' not in url
    assert 'token=' in url
    token = url.split('token=')[1]
    jwt.decode(
        token,
        'test-secret',
        algorithms=['HS256'],
        audience='test-audience',
        issuer='test-issuer',
    )
