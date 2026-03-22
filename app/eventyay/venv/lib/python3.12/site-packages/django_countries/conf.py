from typing import Any, Dict, List

import django.conf


class AppSettings:
    """
    A holder for app-specific default settings that allows overriding via
    the project's settings.
    """

    def __getattribute__(self, attr: str):
        if attr == attr.upper():
            try:
                return getattr(django.conf.settings, attr)
            except AttributeError:
                pass
        return super().__getattribute__(attr)


class Settings(AppSettings):
    COUNTRIES_FLAG_URL = "flags/{code}.gif"
    """
    The URL for a flag.

    It can either be relative to the static url, or an absolute url.

    The location is parsed using Python's string formatting and is passed the
    following arguments:

        * code
        * code_upper

    For example: ``COUNTRIES_FLAG_URL = 'flags/16x10/{code_upper}.png'``
    """

    COUNTRIES_COMMON_NAMES = True
    """
    Whether to use the common names for some countries, as opposed to the
    official ISO name.

    Some examples:
        "Bolivia" instead of "Bolivia, Plurinational State of"
        "South Korea" instead of "Korea (the Republic of)"
        "Taiwan" instead of "Taiwan (Province of China)"
    """

    COUNTRIES_OVERRIDE: Dict[str, Any] = {}
    """
    A dictionary of names to override the defaults.

    Note that you will need to handle translation of customised country names.

    Setting a country's name to ``None`` will exclude it from the country list.
    For example::

        COUNTRIES_OVERRIDE = {
            'NZ': _('Middle Earth'),
            'AU': None
        }
    """

    COUNTRIES_ONLY: Dict[str, Any] = {}
    """
    Similar to COUNTRIES_OVERRIDE
    A dictionary of names to include in selection.

    Note that you will need to handle translation of customised country names.

    For example::

        COUNTRIES_ONLY = {
            'NZ': _('Middle Earth'),
            'AU': _('Desert'),
        }
    """

    COUNTRIES_FIRST: List[str] = []
    """
    Countries matching the country codes provided in this list will be shown
    first in the countries list (in the order specified) before all the
    alphanumerically sorted countries.
    """

    COUNTRIES_FIRST_REPEAT = False
    """
    Countries listed in :attr:`COUNTRIES_FIRST` will be repeated again in the
    alphanumerically sorted list if set to ``True``.
    """

    COUNTRIES_FIRST_BREAK = None
    """
    Countries listed in :attr:`COUNTRIES_FIRST` will be followed by a null
    choice with this title (if set) before all the alphanumerically sorted
    countries.
    """

    COUNTRIES_FIRST_SORT = False
    """
    Countries listed in :attr:`COUNTRIES_FIRST` will be alphanumerically
    sorted based on their translated name instead of relying on their
    order in :attr:`COUNTRIES_FIRST`.
    """

    COUNTRIES_FIRST_BY_LANGUAGE: Dict[str, List[str]] = {}
    """
    A dictionary mapping language codes to lists of countries to show first.

    When set, countries will be ordered based on the user's current language.
    Overrides :attr:`COUNTRIES_FIRST` when a language match is found.

    The dictionary keys can be:
    - Base language codes (e.g., 'fr', 'de', 'en')
    - Full locale codes (e.g., 'en-US', 'fr-CA', 'de-AT')

    The lookup follows this priority:
    1. Exact locale match (e.g., 'en-AU')
    2. Auto-detect from locale + prepend to base language group (requires AUTO_DETECT)
    3. Base language match (e.g., 'en')
    4. Fallback to :attr:`COUNTRIES_FIRST`

    Auto-detection (requires :attr:`COUNTRIES_FIRST_AUTO_DETECT`):
    When AUTO_DETECT is enabled and a full locale code like 'fr-CA' is used,
    the country code (CA) will be automatically extracted and prepended to the
    base language group. For example:
    - User language: 'fr-CA'
    - Settings: {'fr': ['FR', 'CH', 'BE', 'LU']} + AUTO_DETECT = True
    - Result: ['CA', 'FR', 'CH', 'BE', 'LU'] (CA auto-prepended)

    If the auto-detected country is already in the list, it will be moved to the front:
    - User language: 'fr-BE'
    - Settings: {'fr': ['FR', 'CH', 'BE', 'LU']} + AUTO_DETECT = True
    - Result: ['BE', 'FR', 'CH', 'LU'] (BE moved to front)

    Example::

        COUNTRIES_FIRST_BY_LANGUAGE = {
            'fr': ['FR', 'CH', 'BE', 'LU'],  # Francophone countries
            'de': ['DE', 'AT', 'CH', 'LI'],  # Germanic countries
            'en-GB': ['GB', 'IE'],           # Override for British English
        }
    """

    COUNTRIES_FIRST_AUTO_DETECT = False
    """
    Enable automatic country detection from the user's locale.

    When ``True``, automatically extracts the country code from locale codes and
    prepends it to the current first countries list. This is an **independent**
    feature that works with both :attr:`COUNTRIES_FIRST` and
    :attr:`COUNTRIES_FIRST_BY_LANGUAGE`.

    With :attr:`COUNTRIES_FIRST` only::

        COUNTRIES_FIRST_AUTO_DETECT = True
        COUNTRIES_FIRST = ['US', 'GB']
        # en-AU users see: AU, US, GB  (AU prepended)
        # en users see: US, GB         (no country to detect)

    With :attr:`COUNTRIES_FIRST_BY_LANGUAGE`::

        COUNTRIES_FIRST_AUTO_DETECT = True
        COUNTRIES_FIRST_BY_LANGUAGE = {'fr': ['FR', 'CH', 'BE', 'LU']}
        # fr-CA users see: CA, FR, CH, BE, LU  (CA prepended to language group)
        # fr users see: FR, CH, BE, LU         (no country to detect)

    Without this setting, locale country codes are NOT auto-detected, even when
    using :attr:`COUNTRIES_FIRST_BY_LANGUAGE`.
    """


settings = Settings()
