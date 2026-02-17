from django.test import TestCase
from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
from django.utils import translation

class I18nUtilsTest(TestCase):
    def setUp(self):
        get_sorted_grouped_locales.cache_clear()

    def tearDown(self):
        get_sorted_grouped_locales.cache_clear()

    def test_get_sorted_grouped_locales_structure(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales()
        
        self.assertTrue(isinstance(locales, list))
        self.assertTrue(len(locales) > 0)
        
        first = locales[0]
        self.assertIn('code', first)
        self.assertIn('name_translated', first)
        self.assertIn('styled_name', first)
        self.assertIn('variants', first)

    def test_german_variants_grouping(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales()
        
        # Find German
        german = next((l for l in locales if l['code'] == 'de'), None)
        self.assertIsNotNone(german)
        self.assertIn('Deutsch', german['styled_name'])
        
        # Check variants
        variants = german['variants']
        self.assertTrue(len(variants) >= 1) # At least formal
        codes = [v['code'] for v in variants]
        self.assertIn('de-formal', codes)

    def test_sorting_by_translated_name(self):
        # In English, German starts with G. Spanish starts with S.
        translation.activate('en')
        locales = get_sorted_grouped_locales()
        
        codes = [l['code'] for l in locales]
        if 'de' in codes and 'es' in codes:
            self.assertLess(codes.index('de'), codes.index('es')) # G < S
        
        
        translation.activate('de')
        get_sorted_grouped_locales.cache_clear()
        locales_de = get_sorted_grouped_locales()
        codes_de = [l['code'] for l in locales_de]
        
        if 'fr' in codes and 'de' in codes:
            # en: French (F) < German (G)
            self.assertLess(codes.index('fr'), codes.index('de')) 
            
        if 'de' in codes_de and 'fr' in codes_de:
            # de: Deutsch (D) < Französisch (F)
            self.assertLess(codes_de.index('de'), codes_de.index('fr'))

    def test_current_locale_pinning(self):
        # When 'de' is active, it should be the first element
        translation.activate('de')
        locales = get_sorted_grouped_locales('de')
        self.assertEqual(locales[0]['code'], 'de')
        
        # When 'en' is active, it should be the first element
        translation.activate('en')
        locales_en = get_sorted_grouped_locales('en')
        self.assertEqual(locales_en[0]['code'], 'en')

    def test_chinese_splitting(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales()
        codes = [l['code'] for l in locales]
        
        # Check both codes are present as top-level entries (not variants of 'zh')
        self.assertIn('zh-hans', codes)
        self.assertIn('zh-hant', codes)
        
        # Check they have distinct names
        hans_entry = next(l for l in locales if l['code'] == 'zh-hans')
        hant_entry = next(l for l in locales if l['code'] == 'zh-hant')
        
        self.assertNotEqual(hans_entry['styled_name'], hant_entry['styled_name'])

    def test_get_styled_language_name(self):
        from eventyay.helpers.i18n_utils import get_styled_language_name
        
        # Case 1: Translated name != Native name
        # We need a predictable language. 'de' is usually "German" in English and "Deutsch" natively.
        # But get_styled_language_name relies on django's get_language_info, which uses the ACTIVE language for translation.
        # So we must activate English.
        translation.activate('en')
        
        name = get_styled_language_name('de', 'Deutsch')
        self.assertIn('Deutsch', name)
        
        # Case 2: Translated name == Native name (case-insensitive)
        name_en = get_styled_language_name('en', 'English')
        self.assertEqual(name_en, 'English')
        
        # Case 3: Unknown code (fallback)
        name_unknown = get_styled_language_name('xx-yy', 'MyLang')
        self.assertEqual(name_unknown, 'MyLang')

    def test_orphaned_variant(self):
        # mocking settings to simulate incubating parent
        from django.conf import settings
        from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
        
        # Backup original config
        original_config = getattr(settings, '_LANGUAGES_CONFIG', {})
        original_production = getattr(settings, 'IS_PRODUCTION', False)
        
        try:
            # Mock configuration
            settings.IS_PRODUCTION = True
            settings._LANGUAGES_CONFIG = {
                'parent': {'name': 'Parent', 'natural_name': 'Parent', 'incubating': True},
                'variant': {'name': 'Variant', 'natural_name': 'Variant', 'variant_of': 'parent', 'incubating': False}
            }
            
            locales = get_sorted_grouped_locales()
            codes = [l['code'] for l in locales]
            
            # Parent should be missing (incubating + production)
            self.assertNotIn('parent', codes)
            
            # Variant should be present (orphaned but visible)
            self.assertIn('variant', codes)
            
        finally:
            # Restore
            settings._LANGUAGES_CONFIG = original_config
            settings.IS_PRODUCTION = original_production

    def test_label_key_presence(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales()
        
        for item in locales:
            self.assertIn('label', item)
            for variant in item['variants']:
                 # Variants might not have 'label' explicitly set in my code update?
                 # Let's check my code. I added 'label' to variant_entry too.
                 self.assertIn('label', variant)
