import contextlib
from copy import copy

from django.conf import global_settings, settings
from django.utils.translation import activate, get_language
from django.utils.translation.trans_real import get_supported_language_variant

LANGUAGE_CODES_MAPPING = {language.lower(): language for language in settings.LANGUAGES_INFORMATION}
LANGUAGE_NAMES = dict(global_settings.LANGUAGES)
LANGUAGE_NAMES.update(
    (code, language['natural_name']) for code, language in settings.LANGUAGES_INFORMATION.items()
)


def get_language_information(lang: str):
    lang_lower = (lang or '').lower()
    lang_key = LANGUAGE_CODES_MAPPING.get(lang_lower)

    if not lang_key:
        try:
            lang_key = get_supported_language_variant(lang_lower)
        except LookupError:
            lang_key = settings.LANGUAGE_CODE
        # Map the normalized code back to the key in LANGUAGES_INFORMATION
        lang_key = LANGUAGE_CODES_MAPPING.get(lang_key.lower(), settings.LANGUAGE_CODE)

    information = copy(settings.LANGUAGES_INFORMATION[lang_key])
    information['code'] = lang_key
    return information


def get_current_language_information():
    language_code = get_language()
    return get_language_information(language_code)


@contextlib.contextmanager
def language(language_code):
    previous_language = get_language()
    activate(language_code or settings.LANGUAGE_CODE)
    try:
        yield
    finally:
        activate(previous_language)
