from types import SimpleNamespace

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.test.utils import override_settings
from django.utils.timezone import now
from pretix.base.models import Event, Organizer, User

from eventyay.base.middleware import SecurityMiddleware


def get_csp_directive_values(policy: str, directive: str) -> list[str]:
    for part in policy.split('; '):
        if part.startswith(f'{directive} '):
            return part[len(f'{directive} ') :].split(' ')

    raise AssertionError(f'Missing {directive} in Content-Security-Policy')


class LocaleDeterminationTest(TestCase):
    """
    This test case tests various methods around the properties /
    variations concept.
    """

    def setUp(self):
        super().setUp()
        o = Organizer.objects.create(name='Dummy', slug='dummy')
        self.event = Event.objects.create(organizer=o, name='Dummy', slug='dummy', date_from=now(), live=True)
        self.TEST_LOCALE = 'de' if settings.LANGUAGE_CODE == 'en' else 'en'
        self.TEST_LOCALE_LONG = 'de-AT' if settings.LANGUAGE_CODE == 'en' else 'en-NZ'
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')

    def test_global_default(self):
        c = Client()
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, settings.LANGUAGE_CODE)

    def test_browser_default(self):
        c = Client(HTTP_ACCEPT_LANGUAGE=self.TEST_LOCALE)
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, self.TEST_LOCALE)

        c = Client(HTTP_ACCEPT_LANGUAGE=self.TEST_LOCALE_LONG)
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, self.TEST_LOCALE)

    def test_unknown_browser_default(self):
        c = Client(HTTP_ACCEPT_LANGUAGE='sjn')
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, settings.LANGUAGE_CODE)

    def test_cookie_settings(self):
        c = Client()
        cookies = c.cookies
        cookies[settings.LANGUAGE_COOKIE_NAME] = self.TEST_LOCALE
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, self.TEST_LOCALE)

        cookies[settings.LANGUAGE_COOKIE_NAME] = self.TEST_LOCALE_LONG
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, self.TEST_LOCALE)

    def test_user_settings(self):
        c = Client()
        self.user.locale = self.TEST_LOCALE
        self.user.save()
        response = c.post(
            '/control/login',
            {
                'email': 'dummy@dummy.dummy',
                'password': 'dummy',
            },
        )
        self.assertEqual(response.status_code, 302)

        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, self.TEST_LOCALE)

    def test_event_allowed(self):
        self.event.settings.set('locales', ['de', 'en'])
        c = Client()
        cookies = c.cookies
        cookies[settings.LANGUAGE_COOKIE_NAME] = 'de'
        response = c.get('/control/login')
        language = response['Content-Language']
        self.assertEqual(language, 'de')


class SecurityMiddlewareTest(TestCase):
    def setUp(self):
        super().setUp()
        self.organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        self.event = Event.objects.create(
            organizer=self.organizer,
            name='Dummy',
            slug='dummy',
            date_from=now(),
            live=True,
        )
        self.factory = RequestFactory()
        self.middleware = SecurityMiddleware(lambda request: HttpResponse('ok'))

    def build_response(self, path: str, *, event=None, view_name: str | None = None) -> HttpResponse:
        request = self.factory.get(path)
        request.organizer = event.organizer if event else None
        request.event = event
        request.resolver_match = SimpleNamespace(view_name=view_name)
        return self.middleware.process_response(request, HttpResponse('ok'))

    @override_settings(SITE_URL='https://example.com')
    def test_security_middleware_restricts_event_image_hosts(self):
        self.event.settings.set('logo_image', 'HTTPS://CDN.EXAMPLE.COM/header.png')
        self.event.settings.set('event_logo_image', 'http://assets.example.org/logo.png')

        response = self.build_response('/dummy/', event=self.event, view_name='presale:event.index')

        img_src = get_csp_directive_values(response['Content-Security-Policy'], 'img-src')
        assert 'https://cdn.example.com' in img_src
        assert 'http://assets.example.org' in img_src
        assert 'https:' not in img_src
        assert 'http:' not in img_src

    @override_settings(SITE_URL='http://example.com')
    def test_security_middleware_keeps_broad_preview_sources_on_event_settings_page(self):
        response = self.build_response(
            '/event/dummy/dummy/settings/',
            event=self.event,
            view_name='event.update',
        )

        img_src = get_csp_directive_values(response['Content-Security-Policy'], 'img-src')
        assert 'https:' in img_src
        assert 'http:' in img_src

    @override_settings(SITE_URL='https://example.com')
    def test_security_middleware_allows_external_images_on_start_page(self):
        self.event.settings.set('logo_image', 'https://cdn.example.com/header.png')

        response = self.build_response('/', view_name='presale:index')

        img_src = get_csp_directive_values(response['Content-Security-Policy'], 'img-src')
        assert 'https://cdn.example.com' in img_src
