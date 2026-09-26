from bs4 import BeautifulSoup
from django.conf import settings
from django.urls import reverse
from django.test import Client, TestCase
from django.utils.timezone import now
from i18nfield.strings import LazyI18nString

from eventyay.base.models import Event, Organizer
from eventyay.common.utils.language import (
    get_event_enforce_ui_language_cookie_name,
    get_event_language_cookie_name,
)


class LocaleTest(TestCase):
    def test_set_locale_cookie(self):
        response = self.client.get('/control/login')
        assert response['Content-Language'] == 'en'
        self.client.get('/locale/set?locale=de')
        response = self.client.get('/control/login')
        assert response['Content-Language'] == 'de'


class LocaleSwitcherLabelTest(TestCase):
    def setUp(self):
        super().setUp()
        self.organizer = Organizer.objects.create(name='Switcherorg', slug='switcherorg')

    def _get_switcher(self, event):
        response = self.client.get('/%s/%s/' % (event.organizer.slug, event.slug))
        self.assertEqual(response.status_code, 200)
        doc = BeautifulSoup(response.rendered_content, 'lxml')
        summary = doc.select_one('#locale-dropdown-label summary')
        self.assertIsNotNone(summary)
        span = summary.select_one('span.hidden-xs')
        return summary, span

    def test_default_en_event_shows_single_label(self):
        """A default en-only event with an en UI shows 'En', not 'En/En'."""
        event = Event.objects.create(
            organizer=self.organizer,
            name='Default Locale Event',
            slug='defaultlocale',
            date_from=now(),
            live=True,
        )
        summary, span = self._get_switcher(event)
        self.assertEqual(span.get_text(strip=True), 'En')
        self.assertEqual(summary.get('aria-label'), 'Language - En')

    def test_unlinked_de_event_en_ui_shows_dual_label(self):
        """When event and UI languages differ, the dual label stays."""
        event = Event.objects.create(
            organizer=self.organizer,
            name='Unlinked Locale Event',
            slug='unlinkedlocale',
            date_from=now(),
            live=True,
            locale='de',
            locale_array='de,en',
        )
        event.settings.set('locales', ['de', 'en'])
        event.settings.set('locale', 'de')
        enforce_cookie = get_event_enforce_ui_language_cookie_name(event.slug, self.organizer.slug)
        self.client.cookies[enforce_cookie] = '0'
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'

        summary, span = self._get_switcher(event)
        self.assertEqual(span.get_text(strip=True), 'De/En')
        self.assertEqual(summary.get('aria-label'), 'Language - De/En')


class EventLanguageEnforceDefaultTest(TestCase):
    """Tests that 'Link languages' is ON by default for new visitors."""

    def setUp(self):
        super().setUp()
        self.organizer = Organizer.objects.create(name='Testorg', slug='testorg')
        self.event = Event.objects.create(
            organizer=self.organizer,
            name='Test Event',
            slug='testev',
            date_from=now(),
            live=True,
            locale='de',
            locale_array='de,en',
        )
        self.event.settings.set('locales', ['de', 'en'])
        self.event.settings.set('locale', 'de')
        self.enforce_cookie = get_event_enforce_ui_language_cookie_name(
            self.event.slug,
            self.organizer.slug,
        )

    def _get_event_page(self, client=None):
        c = client or self.client
        return c.get('/%s/%s/' % (self.organizer.slug, self.event.slug))

    def test_enforce_defaults_to_on_without_cookie(self):
        """Without the enforce cookie, linking defaults to ON."""
        c = Client()
        response = self._get_event_page(c)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.event_language_enforce_ui)
        self.assertNotIn(self.enforce_cookie, response.cookies)

    def test_enforce_on_syncs_ui_language_to_event_language(self):
        """When enforce is ON and UI language matches an event locale, event language
        mirrors the UI language rather than always defaulting to the event's locale."""
        c = Client(HTTP_ACCEPT_LANGUAGE='en')
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'
        response = self._get_event_page(c)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.event_language_enforce_ui)
        self.assertEqual(response.wsgi_request.event_language, 'en')
        self.assertEqual(response['Content-Language'], 'en')

    def test_enforce_on_global_language_takes_precedence_when_not_in_event_locales(self):
        # Global dropdown language takes precedence; event content falls back to event locale.
        c = Client()
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'fi'
        response = self._get_event_page(c)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.event_language_enforce_ui)
        # Event content falls back to the event's locale ('de')
        self.assertEqual(response.wsgi_request.event_language, 'de')
        # UI stays in the user's chosen language, not overridden by event locale
        self.assertEqual(response['Content-Language'], 'fi')

    def test_enforce_on_default_locale_used_when_ui_outside_event_locales_despite_stale_cookie(self):
        """UI outside event locales should show event content in the default locale, not a stale cookie."""
        self.event.name = LazyI18nString(
            {
                'en': 'English Event Name',
                'gu': 'Gujarati Event Name',
                'de': 'German Event Name',
            }
        )
        self.event.locale = 'gu'
        self.event.locale_array = 'en,gu,de'
        self.event.save()
        self.event.settings.set('locales', ['en', 'gu', 'de'])
        self.event.settings.set('locale', 'gu')

        event_cookie = get_event_language_cookie_name(self.event.slug, self.organizer.slug)
        c = Client()
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'da'
        c.cookies[event_cookie] = 'en'

        response = self._get_event_page(c)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.event_language_enforce_ui)
        self.assertEqual(response.wsgi_request.event_language, 'gu')
        self.assertEqual(response['Content-Language'], 'da')
        self.assertContains(response, 'class="event-title event-public-text-link"')
        self.assertContains(response, 'Gujarati Event Name</a>')

    def test_explicit_enforce_off_is_respected(self):
        """When the enforce cookie is explicitly '0', languages are NOT linked and
        the event language remains the event default regardless of UI language."""
        c = Client(HTTP_ACCEPT_LANGUAGE='en')
        c.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'
        c.cookies[self.enforce_cookie] = '0'
        response = self._get_event_page(c)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.event_language_enforce_ui)
        self.assertEqual(response.wsgi_request.event_language, 'de')
        self.assertEqual(response['Content-Language'], 'en')
        self.assertEqual(c.cookies[self.enforce_cookie].value, '0')

    def test_ui_selection_outside_event_locales_unlinks_languages(self):
        """Selecting an unsupported UI language should auto-disable linking."""
        c = Client()
        c.cookies[self.enforce_cookie] = '1'

        response = c.post(
            reverse('eventyay_common:account.locale'),
            data={
                'locale': 'fr',
                'event': self.event.slug,
                'organizer': self.organizer.slug,
                'next': '/%s/%s/' % (self.organizer.slug, self.event.slug),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[self.enforce_cookie].value, '0')

        event_page = self._get_event_page(c)
        self.assertEqual(event_page.status_code, 200)
        self.assertFalse(event_page.wsgi_request.event_language_enforce_ui)
        self.assertEqual(event_page.wsgi_request.event_language, 'de')
        self.assertEqual(event_page['Content-Language'], 'fr')

    def test_enforce_on_toggle_via_locale_view(self):
        """EventLocaleSet view correctly sets the enforce cookie to '0' when toggled."""
        c = Client()
        # The EventLocaleSet view is mounted at the root /locale/event (locale_patterns)
        # and the event/organizer are passed as GET params so it can look them up.
        url = (
            '/locale/event'
            '?enforce_ui_language=0'
            '&event=%(event)s'
            '&organizer=%(organizer)s'
            '&next=/'
        ) % {'organizer': self.organizer.slug, 'event': self.event.slug}
        response = c.get(url)
        # View should redirect
        self.assertEqual(response.status_code, 302)
        # The enforce cookie should now be explicitly '0'
        self.assertEqual(response.cookies[self.enforce_cookie].value, '0')



