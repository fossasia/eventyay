# ruff: noqa: SIM117
import pytest
from django.test import TestCase
from django.utils import translation

from django_countries import Countries, countries, countries_context
from django_countries.conf import settings


class BaseTest(TestCase):
    def setUp(self):
        del countries.countries

    def tearDown(self):
        del countries.countries


@pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
class TestCountriesFirstByLanguage(BaseTest):
    """Test COUNTRIES_FIRST_BY_LANGUAGE setting with smart auto-prepend."""

    def test_base_language_group(self):
        """Test that base language groups work."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            }
        ):
            # French language should show FR, CH, BE, LU first
            with translation.override("fr"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "FR")
                self.assertEqual(country_list[1].code, "CH")
                self.assertEqual(country_list[2].code, "BE")
                self.assertEqual(country_list[3].code, "LU")

            # Non-French language should show default order (alphabetical)
            with translation.override("en"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AF")  # Afghanistan first

    def test_auto_prepend_from_locale(self):
        """Test that locale country is auto-prepended to base language group."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            COUNTRIES_FIRST_AUTO_DETECT=True,
        ):
            # French Canadian should show CA first, then FR, CH, BE, LU
            with translation.override("fr-CA"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "CA")
                self.assertEqual(country_list[1].code, "FR")
                self.assertEqual(country_list[2].code, "CH")
                self.assertEqual(country_list[3].code, "BE")
                self.assertEqual(country_list[4].code, "LU")

    def test_auto_prepend_deduplication(self):
        """Test that auto-detected country moves to front if already in list."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            COUNTRIES_FIRST_AUTO_DETECT=True,
        ):
            # French Belgian should show BE first, then FR, CH, LU (BE moved to front)
            with translation.override("fr-BE"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "BE")
                self.assertEqual(country_list[1].code, "FR")
                self.assertEqual(country_list[2].code, "CH")
                self.assertEqual(country_list[3].code, "LU")
                # Make sure BE doesn't appear twice
                codes = [c.code for c in country_list[:10]]
                self.assertEqual(codes.count("BE"), 1)

    def test_exact_locale_override(self):
        """Test that exact locale matches override auto-prepend behavior."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
                "fr-CA": ["CA", "US"],  # Explicit override
            }
        ):
            # French Canadian should use explicit override, not auto-prepend
            with translation.override("fr-CA"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "CA")
                self.assertEqual(country_list[1].code, "US")
                # FR should NOT be in first positions
                self.assertNotEqual(country_list[2].code, "FR")

    def test_locale_without_base_language(self):
        """Test auto-detection when no base language group is defined."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "de": ["DE", "AT", "CH"],
            },
            COUNTRIES_FIRST_AUTO_DETECT=True,
        ):
            # en-AU should just show AU first (no base language group)
            with translation.override("en-AU"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AU")

    def test_underscore_locale_format(self):
        """Test that fr_CA format works the same as fr-CA."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            COUNTRIES_FIRST_AUTO_DETECT=True,
        ), translation.override("fr_CA"):
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "CA")
            self.assertEqual(country_list[1].code, "FR")

    def test_multiple_languages(self):
        """Test multiple language groups."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
                "de": ["DE", "AT", "CH", "LI"],
                "es": ["ES", "MX", "AR", "CL"],
            }
        ):
            # French
            with translation.override("fr"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "FR")

            # German
            with translation.override("de"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "DE")

            # Spanish
            with translation.override("es"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "ES")

    def test_fallback_to_static_first(self):
        """Test that it falls back to COUNTRIES_FIRST when language not in map."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            COUNTRIES_FIRST=["US", "CA"],
        ):
            # English should use static COUNTRIES_FIRST
            with translation.override("en"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "US")
                self.assertEqual(country_list[1].code, "CA")

    def test_no_auto_prepend_without_auto_detect_setting(self):
        """Test that BY_LANGUAGE doesn't auto-prepend when AUTO_DETECT is False."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            COUNTRIES_FIRST_AUTO_DETECT=False,  # Explicitly disabled
        ):
            # fr-CA should NOT auto-prepend CA (just use base language group)
            with translation.override("fr-CA"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "FR")
                self.assertEqual(country_list[1].code, "CH")
                self.assertEqual(country_list[2].code, "BE")
                self.assertEqual(country_list[3].code, "LU")

    def test_cache_per_language(self):
        """Test that different languages get different cached results."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR"],
                "de": ["DE"],
            }
        ):
            # First call with French
            with translation.override("fr"):
                fr_list = list(countries)
                self.assertEqual(fr_list[0].code, "FR")

            # Second call with German should NOT return cached French results
            with translation.override("de"):
                de_list = list(countries)
                self.assertEqual(de_list[0].code, "DE")
                self.assertNotEqual(de_list[0].code, "FR")


class TestCountriesContext(BaseTest):
    """Test countries_context() context manager."""

    def test_context_override(self):
        """Test that context manager overrides settings."""
        with self.settings(COUNTRIES_FIRST=["US", "CA"]):
            # Without context, should use settings
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")

            # With context, should override settings
            with countries_context(first=["FR", "DE"]):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "FR")
                self.assertEqual(country_list[1].code, "DE")

            # After context, should revert to settings
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")

    @pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
    def test_context_overrides_language_mapping(self):
        """Test that context can override language mapping explicitly."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            }
        ), translation.override("fr"):
            # Without context, should use language mapping
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "FR")

            # With context disabling language mapping, should use context first
            with countries_context(first=["US", "CA"], first_by_language={}):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "US")
                self.assertEqual(country_list[1].code, "CA")

            # After context, should revert to language mapping
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "FR")

    def test_nested_contexts(self):
        """Test that nested contexts work correctly."""
        with countries_context(first=["US"]):
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")

            with countries_context(first=["FR"]):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "FR")

            # Should revert to outer context
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")

    def test_context_with_empty_list(self):
        """Test that context with empty list works."""
        with self.settings(COUNTRIES_FIRST=["US", "CA"]):
            # Override with empty list
            with countries_context(first=[]):
                country_list = list(countries)
                # Should be alphabetical (no first countries)
                self.assertEqual(country_list[0].code, "AF")

    def test_context_with_only(self):
        """Test that context can override 'only' setting."""
        # Without context, all countries available
        country_list = list(countries)
        self.assertGreater(len(country_list), 10)

        # With context, limit to specific countries
        with countries_context(only=["US", "CA", "MX"]):
            country_list = list(countries)
            self.assertEqual(len(country_list), 3)
            codes = [c.code for c in country_list]
            self.assertIn("US", codes)
            self.assertIn("CA", codes)
            self.assertIn("MX", codes)

    def test_context_with_first_sort(self):
        """Test that context can override 'first_sort' setting."""
        with self.settings(COUNTRIES_FIRST=["US", "GB", "AU"]):
            # Without first_sort
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")
            self.assertEqual(country_list[1].code, "GB")
            self.assertEqual(country_list[2].code, "AU")

            # With first_sort in context
            with countries_context(first_sort=True):
                country_list = list(countries)
                # Should be alphabetically sorted: AU, GB, US
                self.assertEqual(country_list[0].code, "AU")
                self.assertEqual(country_list[1].code, "GB")
                self.assertEqual(country_list[2].code, "US")

    def test_context_with_first_repeat(self):
        """Test that context can override 'first_repeat' setting."""
        with self.settings(COUNTRIES_FIRST=["US"], COUNTRIES_FIRST_REPEAT=False):
            # Without repeat, US appears only once
            country_list = list(countries)
            codes = [c.code for c in country_list]
            self.assertEqual(codes.count("US"), 1)

            # With repeat in context
            with countries_context(first_repeat=True):
                country_list = list(countries)
                codes = [c.code for c in country_list]
                # US should appear twice: once first, once in alphabetical
                self.assertEqual(codes.count("US"), 2)

    def test_context_with_first_break(self):
        """Test that context can override 'first_break' setting."""
        with self.settings(COUNTRIES_FIRST=["US", "CA"]):
            # Without break
            country_list = list(countries)
            # Third item should be a real country
            self.assertNotEqual(country_list[2].code, "")

            # With break in context
            with countries_context(first_break="───────"):
                country_list = list(countries)
                # Third item should be the break separator
                self.assertEqual(country_list[2].code, "")
                self.assertEqual(country_list[2].name, "───────")


@pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
class TestPerFieldCustomization(BaseTest):
    """Test that custom Countries classes work with language mapping."""

    def test_custom_countries_class_with_first_by_language(self):
        """Test that custom Countries class can have its own first_by_language."""

        class CustomCountries(Countries):
            first_by_language = {
                "en": ["NZ", "AU"],
            }

        custom = CustomCountries()

        with translation.override("en"):
            country_list = list(custom)
            self.assertEqual(country_list[0].code, "NZ")
            self.assertEqual(country_list[1].code, "AU")

    def test_custom_countries_class_overrides_global_setting(self):
        """Test that custom Countries class overrides global setting."""

        class CustomCountries(Countries):
            first_by_language = {
                "fr": ["CA", "FR"],  # Different from global
            }

        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            }
        ):
            # Global countries should use global setting
            with translation.override("fr"):
                global_list = list(countries)
                self.assertEqual(global_list[0].code, "FR")

                # Custom instance should use its own setting
                custom = CustomCountries()
                custom_list = list(custom)
                self.assertEqual(custom_list[0].code, "CA")
                self.assertEqual(custom_list[1].code, "FR")


@pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
class TestCountriesAutoDetect(BaseTest):
    """Test COUNTRIES_FIRST_AUTO_DETECT setting."""

    def test_auto_detect_basic(self):
        """Test basic auto-detection from locale."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            # en-AU should show AU first (just AU, no COUNTRIES_FIRST set)
            with translation.override("en-AU"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AU")
                # Second should be alphabetical
                self.assertEqual(country_list[1].code, "AF")

    def test_auto_detect_various_locales(self):
        """Test auto-detection with various locale codes."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            # French Canadian
            with translation.override("fr-CA"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "CA")

            # German Austrian
            with translation.override("de-AT"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AT")

            # Spanish Mexican
            with translation.override("es-MX"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "MX")

    def test_auto_detect_with_underscore(self):
        """Test that underscore format works (fr_CA)."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            with translation.override("en_AU"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AU")

    def test_auto_detect_combines_with_countries_first(self):
        """Test that auto-detected country is prepended to COUNTRIES_FIRST."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ):
            # en-AU should show AU, US, GB
            with translation.override("en-AU"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AU")
                self.assertEqual(country_list[1].code, "US")
                self.assertEqual(country_list[2].code, "GB")

    def test_auto_detect_deduplication_with_countries_first(self):
        """Test auto-detected country moves to front if in COUNTRIES_FIRST."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB", "AU"],
        ):
            # en-AU should show AU, US, GB (AU moved to front)
            with translation.override("en-AU"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AU")
                self.assertEqual(country_list[1].code, "US")
                self.assertEqual(country_list[2].code, "GB")
                # Make sure AU doesn't appear twice
                codes = [c.code for c in country_list[:10]]
                self.assertEqual(codes.count("AU"), 1)

    def test_auto_detect_without_country(self):
        """Test that base language (no country) falls back to COUNTRIES_FIRST."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ):
            # Just 'en' should fall back to COUNTRIES_FIRST
            with translation.override("en"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "US")
                self.assertEqual(country_list[1].code, "GB")

    def test_auto_detect_with_empty_first(self):
        """Test auto-detect with no fallback."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            # Base language with no COUNTRIES_FIRST should be alphabetical
            with translation.override("en"):
                country_list = list(countries)
                self.assertEqual(country_list[0].code, "AF")  # Afghanistan

    def test_auto_detect_disabled_by_default(self):
        """Test that auto-detect is disabled by default."""
        # Without setting COUNTRIES_FIRST_AUTO_DETECT
        with translation.override("en-AU"):
            country_list = list(countries)
            # Should be alphabetical, not AU first
            self.assertEqual(country_list[0].code, "AF")

    def test_language_mapping_takes_precedence(self):
        """Test that BY_LANGUAGE takes precedence over AUTO_DETECT."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST_BY_LANGUAGE={
                "en": ["US", "GB"],
            },
        ):
            # en-AU should use language mapping, not pure auto-detect
            with translation.override("en-AU"):
                country_list = list(countries)
                # Should get AU auto-prepended to the 'en' group
                self.assertEqual(country_list[0].code, "AU")
                self.assertEqual(country_list[1].code, "US")
                self.assertEqual(country_list[2].code, "GB")

    def test_auto_detect_per_field(self):
        """Test that per-field auto-detect works."""

        class AutoDetectCountries(Countries):
            first_auto_detect = True

        custom = AutoDetectCountries()

        with translation.override("en-NZ"):
            country_list = list(custom)
            self.assertEqual(country_list[0].code, "NZ")


class TestCountriesLength(BaseTest):
    """Test that __len__ works correctly with dynamic first countries."""

    @pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
    def test_len_with_language_mapping(self):
        """Test that length calculation works with language-based first countries."""
        with self.settings(
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE"],
            }
        ), translation.override("fr"):
            # Length should account for first countries
            length = len(countries)
            # Base countries (249) + first countries (3) = 252
            # (COUNTRIES_FIRST_REPEAT defaults to False)
            self.assertEqual(length, 249 + 3)

    def test_len_with_context(self):
        """Test that length calculation works with context override."""
        with countries_context(first=["US", "CA"]):
            length = len(countries)
            self.assertEqual(length, 249 + 2)

    @pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
    def test_len_with_auto_detect(self):
        """Test that length calculation works with auto-detect."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            with translation.override("en-AU"):
                length = len(countries)
                # 249 countries + 1 auto-detected
                self.assertEqual(length, 249 + 1)

    @pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
    def test_len_with_auto_detect_and_countries_first(self):
        """Test length with auto-detect combined with COUNTRIES_FIRST."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ), translation.override("en-AU"):
            length = len(countries)
            # 249 countries + 3 first (AU, US, GB)
            self.assertEqual(length, 249 + 3)


@pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
class TestBrowserLanguageDetection(BaseTest):
    """
    Test auto-detect with browser Accept-Language header simulation.

    These tests simulate how COUNTRIES_FIRST_AUTO_DETECT works with real
    browser language preferences, like a user visiting from Australia with
    their browser set to "en-AU" or a French-Canadian user with "fr-CA".

    In production, Django's LocaleMiddleware parses the Accept-Language header
    and activates the appropriate language. These tests simulate that flow.
    """

    def _parse_accept_language(self, accept_language):
        """
        Parse Accept-Language header and return best language code.

        This simulates what Django's LocaleMiddleware does when processing
        the HTTP Accept-Language header from a browser.
        """
        from django.utils.translation import trans_real

        # Parse the Accept-Language header
        parsed = trans_real.parse_accept_lang_header(accept_language)
        if not parsed:
            return None

        # Get the first (highest priority) language
        # Format: [(lang, priority), ...] sorted by priority
        return parsed[0][0].lower()

    def test_australian_browser_auto_detect(self):
        """Test that Australian browser (en-AU) gets Australia first."""
        with self.settings(COUNTRIES_FIRST_AUTO_DETECT=True):
            # Simulate browser sending Accept-Language: en-AU
            language = self._parse_accept_language("en-AU")
            self.assertEqual(language, "en-au")

            # Activate the language like Django's LocaleMiddleware would
            with translation.override(language):
                country_list = list(countries)

                # Verify AU is first
                self.assertEqual(country_list[0].code, "AU")
                # Second should be alphabetical
                self.assertEqual(country_list[1].code, "AF")

    def test_canadian_french_browser_with_language_mapping(self):
        """Test French-Canadian browser with language-based first countries."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
        ):
            # Simulate browser sending Accept-Language: fr-CA
            language = self._parse_accept_language("fr-CA")
            self.assertEqual(language, "fr-ca")

            # Activate the language like Django's LocaleMiddleware would
            with translation.override(language):
                country_list = list(countries)

                # Should get CA prepended to French group
                self.assertEqual(country_list[0].code, "CA")
                self.assertEqual(country_list[1].code, "FR")
                self.assertEqual(country_list[2].code, "CH")
                self.assertEqual(country_list[3].code, "BE")

    def test_multiple_language_preferences(self):
        """Test browser with multiple language preferences in Accept-Language."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ):
            # Browser prefers Spanish-Mexican, then English
            # Accept-Language: es-MX,es;q=0.9,en;q=0.8
            language = self._parse_accept_language("es-MX,es;q=0.9,en;q=0.8")

            # Django should pick es-mx as the highest priority
            self.assertEqual(language, "es-mx")

            # Activate the language like Django's LocaleMiddleware would
            with translation.override(language):
                country_list = list(countries)

                # Should get MX prepended to COUNTRIES_FIRST
                self.assertEqual(country_list[0].code, "MX")
                self.assertEqual(country_list[1].code, "US")
                self.assertEqual(country_list[2].code, "GB")

    def test_german_swiss_browser(self):
        """Test German-Swiss browser (de-CH) with language mapping."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST_BY_LANGUAGE={
                "de": ["DE", "AT", "CH", "LI"],
            },
        ):
            # Simulate browser sending Accept-Language: de-CH
            language = self._parse_accept_language("de-CH")
            self.assertEqual(language, "de-ch")

            # Activate the language like Django's LocaleMiddleware would
            with translation.override(language):
                country_list = list(countries)

                # CH should move to front (deduplication)
                self.assertEqual(country_list[0].code, "CH")
                self.assertEqual(country_list[1].code, "DE")
                self.assertEqual(country_list[2].code, "AT")
                self.assertEqual(country_list[3].code, "LI")
                # Make sure CH only appears once
                codes = [c.code for c in country_list[:10]]
                self.assertEqual(codes.count("CH"), 1)

    def test_base_language_without_country(self):
        """Test browser sending only base language (no country code)."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ):
            # Simulate browser sending Accept-Language: en (no country)
            language = self._parse_accept_language("en")

            # Language detected as just 'en'
            self.assertIn(language, ["en", "en-us"])  # Depends on Django version

            # Activate the language like Django's LocaleMiddleware would
            with translation.override(language):
                country_list = list(countries)

                # No country to detect, should fall back to COUNTRIES_FIRST
                self.assertEqual(country_list[0].code, "US")
                self.assertEqual(country_list[1].code, "GB")

    def test_empty_accept_language(self):
        """Test browser with empty Accept-Language header."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
        ):
            # Simulate browser with no Accept-Language header
            language = self._parse_accept_language("")

            # Should return None for empty header
            self.assertIsNone(language)

            # Without a language, auto-detect can't work, falls back to default
            country_list = list(countries)
            self.assertEqual(country_list[0].code, "US")
            self.assertEqual(country_list[1].code, "GB")

    def test_unsupported_language_falls_back(self):
        """Test browser with unsupported language still works."""
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US"],
        ):
            # Simulate browser sending zh-CN (which IS in Django's default LANGUAGES)
            language = self._parse_accept_language("zh-CN")
            # Django supports zh-hans, so zh-cn will be normalized
            self.assertIsNotNone(language)

            # Activate the language
            with translation.override(language):
                country_list = list(countries)
                # CN should be auto-detected from the locale
                self.assertEqual(country_list[0].code, "CN")


# Define a view for middleware tests
def country_view_for_tests(request):
    """
    Simple view that returns the country list and current language.

    This simulates a real view where a form with CountryField is rendered.
    """
    from django.http import JsonResponse

    country_list = list(countries)
    return JsonResponse(
        {
            "language": translation.get_language(),
            "countries": [{"code": c.code, "name": c.name} for c in country_list[:5]],
        }
    )


# URL patterns for middleware tests
test_urlpatterns = [
    __import__("django.urls").urls.path("countries/", country_view_for_tests),
]


@pytest.mark.skipif(not settings.USE_I18N, reason="No i18n")
class TestBrowserLanguageViaMiddleware(BaseTest):
    """
    Test auto-detect through actual Django middleware and views.

    These tests make HTTP requests through Django's test client, simulating
    how browsers send Accept-Language headers in production. The requests
    are processed through LocaleMiddleware, which activates the language.
    """

    def test_australian_browser_via_middleware(self):
        """
        Test that Australian browser (Accept-Language: en-AU) gets AU first.

        This simulates a real user from Australia visiting a form with a
        CountryField. Their browser sends 'en-AU' which Django's LocaleMiddleware
        detects, and COUNTRIES_FIRST_AUTO_DETECT uses to show Australia first.

        Note: Django's default LANGUAGES setting includes 'en-au', so we don't
        need to explicitly configure it.
        """
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            MIDDLEWARE=[
                "django.middleware.common.CommonMiddleware",
                "django.middleware.locale.LocaleMiddleware",
            ],
            ROOT_URLCONF="django_countries.tests.test_dynamic_first",
        ):
            response = self.client.get("/countries/", HTTP_ACCEPT_LANGUAGE="en-AU")

            self.assertEqual(response.status_code, 200)
            data = response.json()

            # LocaleMiddleware should have activated en-au
            self.assertEqual(data["language"], "en-au")

            # AU should be first in the list
            self.assertEqual(data["countries"][0]["code"], "AU")

    def test_french_canadian_with_language_mapping(self):
        """
        Test French-Canadian browser with language-based country mapping.

        A user from Quebec has their browser set to 'fr-CA'. Since Django's
        default LANGUAGES doesn't include 'fr-ca', LocaleMiddleware falls back
        to 'fr'. To get full auto-detect functionality, add specific locales
        to LANGUAGES. This test demonstrates the feature WITH configuration.
        """
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST_BY_LANGUAGE={
                "fr": ["FR", "CH", "BE", "LU"],
            },
            MIDDLEWARE=[
                "django.middleware.common.CommonMiddleware",
                "django.middleware.locale.LocaleMiddleware",
            ],
            # Add fr-ca so LocaleMiddleware doesn't fall back to fr
            LANGUAGES=[
                ("en", "English"),
                ("fr", "French"),
                ("fr-ca", "French (Canada)"),
            ],
            ROOT_URLCONF="django_countries.tests.test_dynamic_first",
        ):
            response = self.client.get("/countries/", HTTP_ACCEPT_LANGUAGE="fr-CA")

            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Should detect fr-ca (with explicit LANGUAGES configuration)
            self.assertEqual(data["language"], "fr-ca")

            # Should see CA prepended to French group
            self.assertEqual(data["countries"][0]["code"], "CA")
            self.assertEqual(data["countries"][1]["code"], "FR")
            self.assertEqual(data["countries"][2]["code"], "CH")

    def test_complex_accept_language_header(self):
        """
        Test browser with multiple languages and quality values.

        Modern browsers send complex Accept-Language headers like:
        'es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7'

        LocaleMiddleware parses quality values and picks the highest priority
        language, which should be es-MX, showing MX first in the country list.

        Note: Django's default LANGUAGES includes 'es-mx'.
        """
        with self.settings(
            COUNTRIES_FIRST_AUTO_DETECT=True,
            COUNTRIES_FIRST=["US", "GB"],
            MIDDLEWARE=[
                "django.middleware.common.CommonMiddleware",
                "django.middleware.locale.LocaleMiddleware",
            ],
            ROOT_URLCONF="django_countries.tests.test_dynamic_first",
        ):
            response = self.client.get(
                "/countries/",
                HTTP_ACCEPT_LANGUAGE="es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Should pick es-mx (highest priority)
            self.assertEqual(data["language"], "es-mx")

            # MX should be prepended to COUNTRIES_FIRST
            self.assertEqual(data["countries"][0]["code"], "MX")
            self.assertEqual(data["countries"][1]["code"], "US")
            self.assertEqual(data["countries"][2]["code"], "GB")


urlpatterns = test_urlpatterns  # Make urlpatterns available at module level
