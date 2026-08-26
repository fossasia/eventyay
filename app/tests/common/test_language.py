from django.conf import settings

from eventyay.common.language import get_ui_language_options


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
