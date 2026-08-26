import contextlib
from collections import Counter
from copy import copy
from functools import lru_cache

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
    codes_in_order = [code for code, __ in settings.LANGUAGES]

    if codes is not None:
        requested_codes = {code.lower() for code in codes}
        codes_in_order = [code for code in codes_in_order if code.lower() in requested_codes]

    with translation.override('en'):
        english_names = {
            code: str(settings.LANGUAGES_INFORMATION.get(code, {}).get('name', code))
            for code in codes_in_order
        }
    sorted_codes = sorted(codes_in_order, key=lambda code: (english_names.get(code, code).casefold(), code))

    choices = []
    for code in sorted_codes:
        language_info = settings.LANGUAGES_INFORMATION.get(code, {})
        natural_name = language_info.get('natural_name') or english_names.get(code, code)
        english_name = english_names.get(code, code)
        if natural_name.strip().casefold() == english_name.strip().casefold():
            label = natural_name
        else:
            label = f'\u200e{natural_name} ({english_name})'
        choices.append((code, label))
    return choices


@lru_cache(maxsize=None)
def _native_language_name(code: str) -> str:
    language_info = settings.LANGUAGES_INFORMATION.get(code, {})
    language_name = language_info.get('name')
    if language_name is None:
        return code
    with translation.override(code):
        return str(language_name)


def get_ui_language_options(codes=None) -> list[dict]:
    """Language picker entries used by tickets, talk, and Video.

    Labels match ``fragment_language_switch.html``: native name, with extra
    disambiguation when two locales share the same native name.
    """
    available_codes = [code for code, __ in settings.LANGUAGES]
    ordered_codes = [code for code, __ in get_language_choices_native_with_ui_name(codes if codes is not None else available_codes)]
    supported_languages = [
        (code, settings.LANGUAGES_INFORMATION.get(code, {}).get('natural_name', code))
        for code in ordered_codes
    ]
    natural_name_counts = Counter(natural_name for __, natural_name in supported_languages)
    labels_by_code = {}
    for code, natural_name in supported_languages:
        label = natural_name
        if natural_name_counts[natural_name] > 1:
            native_language_name = _native_language_name(code)
            if native_language_name:
                label = native_language_name
        labels_by_code[code] = label

    label_counts = Counter(labels_by_code.values())
    options = []
    for code, __ in supported_languages:
        label = labels_by_code[code]
        if label_counts[label] > 1:
            label = f'{label} ({code})'
        options.append({'code': code, 'label': label, 'nativeLabel': label})
    return options


@contextlib.contextmanager
def language(language_code):
    previous_language = get_language()
    activate(language_code or settings.LANGUAGE_CODE)
    try:
        yield
    finally:
        activate(previous_language)
