import contextlib
from copy import copy

from django.conf import global_settings, settings
from django.utils import translation
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


def get_language_choices_native_with_ui_name(codes=None) -> list[tuple[str, str]]:
    translated_names = dict(settings.LANGUAGES)
    codes_in_order = [code for code, __ in settings.LANGUAGES]

    if codes is not None:
        requested_codes = {code.lower() for code in codes}
        codes_in_order = [code for code in codes_in_order if code.lower() in requested_codes]

    with translation.override('en'):
        english_names = {
            code: str(dict(settings.LANGUAGES).get(code, settings.LANGUAGES_INFORMATION.get(code, {}).get('name', code)))
            for code in codes_in_order
        }
    sorted_codes = sorted(codes_in_order, key=lambda code: (english_names.get(code, code).casefold(), code))

    choices = []
    for code in sorted_codes:
        language_info = settings.LANGUAGES_INFORMATION.get(code, {})
        natural_name = language_info.get('natural_name') or str(translated_names.get(code, code))
        translated_name = str(translated_names.get(code, language_info.get('name', code)))
        choices.append((code, f'{natural_name} ({translated_name})'))
    return choices


@contextlib.contextmanager
def language(language_code):
    previous_language = get_language()
    activate(language_code or settings.LANGUAGE_CODE)
    try:
        yield
    finally:
        activate(previous_language)
