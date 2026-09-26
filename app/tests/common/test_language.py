import pytest
from django.conf import settings

from eventyay.common.language import get_locale_switcher_label, get_ui_language_options


def test_get_ui_language_options_uses_django_language_codes():
    options = get_ui_language_options()
    option_codes = [item['code'] for item in options]
    django_codes = [code for code, __ in settings.LANGUAGES]

    assert set(option_codes) == set(django_codes)
    assert all(item.get('nativeLabel') for item in options)
    assert 'uk' in option_codes
    assert 'ua' not in option_codes
    assert 'pt-br' in option_codes
    assert 'zh-hans' in option_codes


@pytest.mark.parametrize(
    'event_language,ui_language,expected',
    (
        ('en', 'en', 'En'),
        ('de', 'de', 'De'),
        ('de', 'en', 'De/En'),
        ('en', 'de', 'En/De'),
        ('en-gb', 'en', 'En'),
        ('de-formal', 'de', 'De'),
        ('pt-br', 'pt-pt', 'Pt'),
        ('fr', 'fr', 'Fr'),
    ),
)
def test_get_locale_switcher_label(event_language, ui_language, expected):
    assert get_locale_switcher_label(event_language, ui_language) == expected
