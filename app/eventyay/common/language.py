import contextlib
from copy import copy
from typing import Iterable

from django.conf import global_settings, settings
from django.utils.translation import activate, get_language
from django.utils.translation.trans_real import get_supported_language_variant

LANGUAGE_CODES_MAPPING = {language.lower(): language for language in settings.LANGUAGES_INFORMATION}
BACKEND_LANGUAGE_NAMES = dict(settings.LANGUAGES)
LANGUAGE_NAMES = dict(global_settings.LANGUAGES)
LANGUAGE_NAMES.update(
    (code, language['natural_name']) for code, language in settings.LANGUAGES_INFORMATION.items()
)


def get_language_display_names(codes: Iterable[str], prefer_natural_name: bool = True) -> list[tuple[str, str]]:
    """
    Build language labels for the given locale codes with deterministic disambiguation.
    We default to native names, but if a locale variant would otherwise look identical
    to its base language (e.g. de/de-formal, nl/nl-informal), we use the backend label.
    """
    normalized_codes = list(codes)
    labels = {}

    for code in normalized_codes:
        info = settings.LANGUAGES_INFORMATION.get(code, {})
        backend_label = BACKEND_LANGUAGE_NAMES.get(code) or info.get('name') or code
        natural_label = info.get('natural_name') or backend_label
        label = natural_label if prefer_natural_name else backend_label

        base_code = info.get('public_code')
        if base_code:
            normalized_base_code = str(base_code).lower().replace('_', '-')
            normalized_base_code = LANGUAGE_CODES_MAPPING.get(normalized_base_code, normalized_base_code)
            base_info = settings.LANGUAGES_INFORMATION.get(normalized_base_code)
            if base_info and natural_label == (base_info.get('natural_name') or ''):
                label = backend_label

        labels[code] = str(label)

    duplicate_groups = {}
    for code, label in labels.items():
        duplicate_groups.setdefault(label.casefold(), []).append(code)

    for group in duplicate_groups.values():
        if len(group) > 1:
            for code in group:
                info = settings.LANGUAGES_INFORMATION.get(code, {})
                labels[code] = str(BACKEND_LANGUAGE_NAMES.get(code) or info.get('name') or code)

    return [(code, labels[code]) for code in normalized_codes]


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
