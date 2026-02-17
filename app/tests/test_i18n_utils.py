from django.test import TestCase
from eventyay.helpers.i18n_utils import get_sorted_grouped_locales
from django.utils import translation

class I18nUtilsTest(TestCase):
    def test_get_sorted_grouped_locales_structure(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales('en')
        
        self.assertTrue(isinstance(locales, list))
        self.assertTrue(len(locales) > 0)
        
        first = locales[0]
        self.assertIn('code', first)
        self.assertIn('name_translated', first)
        self.assertIn('styled_name', first)
        self.assertIn('variants', first)

    def test_german_variants_grouping(self):
        translation.activate('en')
        locales = get_sorted_grouped_locales('en')
        
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
        locales = get_sorted_grouped_locales('en')
        
        codes = [l['code'] for l in locales]
        if 'de' in codes and 'es' in codes:
            self.assertLess(codes.index('de'), codes.index('es')) # G < S
        
        translation.activate('de')
        locales_de = get_sorted_grouped_locales('de')
        codes_de = [l['code'] for l in locales_de]
        
        if 'fr' in codes and 'de' in codes:
            # en: French (F) < German (G)
            self.assertLess(codes.index('fr'), codes.index('de')) 
            
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
        locales = get_sorted_grouped_locales('en')
        codes = [l['code'] for l in locales]
        
        # Check both codes are present as top-level entries (not variants of 'zh')
        self.assertIn('zh-hans', codes)
        self.assertIn('zh-hant', codes)
        
        # Check they have distinct names
        hans_entry = next(l for l in locales if l['code'] == 'zh-hans')
        hant_entry = next(l for l in locales if l['code'] == 'zh-hant')
        
        self.assertNotEqual(hans_entry['styled_name'], hant_entry['styled_name'])


