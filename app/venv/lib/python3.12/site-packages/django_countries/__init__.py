#!/usr/bin/env python
import itertools
import re
from contextlib import contextmanager
from gettext import NullTranslations
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Literal,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
    overload,
)

from asgiref.local import Local
from django.utils.encoding import force_str
from django.utils.translation import get_language, override, trans_real

from django_countries.conf import settings

from .base import CountriesBase

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise

    class ComplexCountryName(TypedDict, total=False):
        name: "StrPromise"
        names: "List[StrPromise]"
        alpha3: str
        numeric: int
        ioc_code: str
        flag_url: str

    CountryName = Union[
        StrPromise,  # type: ignore
        ComplexCountryName,
    ]
    CountryCode = Union[str, int, None]


try:
    import pyuca  # type: ignore

    collator = pyuca.Collator()

    # Use UCA sorting if it's available.
    def sort_key(item: Tuple[str, str]) -> Any:
        return collator.sort_key(item[1])

except ImportError:
    # Fallback if the UCA sorting is not available.
    import unicodedata

    # Cheap and dirty method to sort against ASCII characters only.
    def sort_key(item: Tuple[str, str]) -> Any:
        return (
            unicodedata.normalize("NFKD", item[1])
            .encode("ascii", "ignore")
            .decode("ascii")
        )


_translation_state = Local()
_countries_context = Local()


@contextmanager
def countries_context(**options):
    """
    Context manager to temporarily override country options for the current thread.

    Supports all country configuration options:
        - first: List of countries to show first
        - only: Limit to specific countries
        - first_sort: Sort first countries alphabetically
        - first_repeat: Repeat first countries in main list
        - first_break: Separator text between first and main list
        - first_by_language: Language-based country ordering mapping
        - first_auto_detect: Auto-detect country from locale

    Examples:
        # Override first countries
        with countries_context(first=['FR', 'BE', 'LU']):
            form = MyForm()  # Will show FR, BE, LU first

        # Limit to specific countries
        with countries_context(only=['US', 'CA', 'MX'], first=['US']):
            form = RegionalForm()  # Only North American countries

        # Sort first countries alphabetically
        with countries_context(first=['US', 'GB', 'AU'], first_sort=True):
            form = MyForm()  # Shows AU, GB, US (sorted)

        # Override language-based ordering with custom first list
        with countries_context(first=['US', 'CA'], first_by_language={}):
            form = MyForm()  # Disables language mapping, uses custom first

    Context options override their corresponding settings (e.g., first overrides
    COUNTRIES_FIRST, first_by_language overrides COUNTRIES_FIRST_BY_LANGUAGE).
    Each option works independently - you can override some while leaving others
    to use global settings.

    This allows dynamic, per-request customization of country options without
    modifying global settings. Commonly used in middleware or views to set
    country order based on user preferences, IP geolocation, etc.

    Args:
        **options: Country options to override (first, only, first_sort,
                   first_repeat, first_break, first_by_language, first_auto_detect)
    """
    # Store previous context
    previous_context = getattr(_countries_context, "options", None)

    # Set new context
    _countries_context.options = options

    try:
        yield
    finally:
        # Restore previous context
        if previous_context is not None:
            _countries_context.options = previous_context
        elif hasattr(_countries_context, "options"):
            del _countries_context.options


class EmptyFallbackTranslator(NullTranslations):
    def gettext(self, message: str) -> str:
        if not getattr(_translation_state, "fallback", True):
            # Interrupt the fallback chain.
            return ""
        return super().gettext(message)


@contextmanager
def no_translation_fallback():
    if not settings.USE_I18N:
        yield
        return
    # Ensure the empty fallback translator has been installed.
    catalog = trans_real.catalog()
    original_fallback = catalog._fallback  # type: ignore
    if not isinstance(original_fallback, EmptyFallbackTranslator):
        empty_fallback_translator = EmptyFallbackTranslator()
        empty_fallback_translator._fallback = original_fallback  # type: ignore
        catalog._fallback = empty_fallback_translator  # type: ignore
    # Set the translation state to not use a fallback while inside this context.
    _translation_state.fallback = False
    try:
        yield
    finally:
        _translation_state.fallback = True


class AltCodes(NamedTuple):
    alpha3: str
    numeric: Optional[int]


class CountryTuple(NamedTuple):
    code: str
    name: str

    def __repr__(self) -> str:
        """
        Display the repr as a standard tuple for better backwards
        compatibility with outputting this in a template.
        """
        return f"({self.code!r}, {self.name!r})"


class Countries(CountriesBase):
    """
    An object containing a list of ISO3166-1 countries.

    Iterating this object will return the countries as namedtuples (of
    the country ``code`` and ``name``), sorted by name.
    """

    _countries: Dict[str, "CountryName"]
    _alt_codes: Dict[str, AltCodes]

    def _resolve_first_countries(self) -> List[str]:
        """
        Resolve which countries should be shown first.

        Each setting is independently resolved via get_option(), which checks:
        1. Thread-local context (highest priority)
        2. Instance attribute (custom Countries subclass)
        3. Global Django setting

        Resolution flow:
        1. If COUNTRIES_FIRST_BY_LANGUAGE is set:
           a. Check for exact locale match (e.g., 'fr-CA' key)
           b. If COUNTRIES_FIRST_AUTO_DETECT enabled and locale has country:
              - Extract country from locale (e.g., 'fr-CA' → 'CA')
              - Prepend to base language group (e.g., ['FR', 'CH'] → ['CA', 'FR', 'CH'])
           c. Check for base language match (e.g., 'fr' key)
        2. If COUNTRIES_FIRST_AUTO_DETECT enabled (without language mapping):
           - Extract country from locale and prepend to COUNTRIES_FIRST
        3. Fall back to COUNTRIES_FIRST

        Note: To disable language-based ordering in context, explicitly set
        first_by_language={} rather than just setting first=[...].
        """
        # Get auto-detect setting (checks context, instance, then settings)
        auto_detect: bool = self.get_option("first_auto_detect") or False

        # Get language-based mapping (checks context, instance, then settings)
        by_language: Dict[str, List[str]] = self.get_option("first_by_language") or {}

        if by_language:
            language = get_language()
            if language:
                # Normalize the by_language dict to handle case-insensitive lookups
                # Django uses lowercase locale codes (e.g., 'fr-ca'), but users may
                # write 'fr-CA' in settings
                by_language_normalized = {k.lower(): v for k, v in by_language.items()}

                # 1. Check for exact locale match (e.g., 'en-au')
                if language.lower() in by_language_normalized:
                    return by_language_normalized[language.lower()]

                # 2. Auto-detect from locale and prepend to base language group
                # Only if COUNTRIES_FIRST_AUTO_DETECT is enabled
                if auto_detect and ("-" in language or "_" in language):
                    # Support both fr-ca and fr_ca formats
                    separator = "-" if "-" in language else "_"
                    parts = language.split(separator)
                    if len(parts) == 2:
                        base_lang = parts[0].lower()
                        country_code = parts[1].upper()

                        # Get base language group if it exists
                        base_group = by_language_normalized.get(base_lang, [])

                        # Create new list with auto-detected country prepended
                        result = []
                        if country_code:
                            result.append(country_code)

                        # Add base group countries, skipping duplicates
                        for code in base_group:
                            if code not in result:
                                result.append(code)

                        # If we have a result with auto-detected country, return it
                        if result:
                            return result

                # 3. Fall back to base language match (e.g., 'en')
                base_lang = language.split("-")[0].split("_")[0].lower()
                if base_lang in by_language_normalized:
                    return by_language_normalized[base_lang]

        # Check for pure auto-detect mode (no language mapping)
        if auto_detect:
            language = get_language()
            if language and ("-" in language or "_" in language):
                # Extract country code from locale (e.g., 'en-au' -> 'AU')
                separator = "-" if "-" in language else "_"
                parts = language.split(separator)
                if len(parts) == 2:
                    country_code = parts[1].upper()
                    if country_code:
                        # Combine auto-detected with COUNTRIES_FIRST
                        fallback_first: List[str] = self.get_option("first") or []
                        # Prepend auto-detected country, removing duplicates
                        result = [country_code]
                        for code in fallback_first:
                            if code not in result:
                                result.append(code)
                        return result

        # Fall back to static COUNTRIES_FIRST
        return self.get_option("first") or []

    def get_option(self, option: str):
        """
        Get a configuration option, checking in this order:
        1. Thread-local context (from countries_context())
        2. Instance attributes
        3. Django project settings
        """
        # Check thread-local context first
        context_options = getattr(_countries_context, "options", None)
        if context_options and option in context_options:
            return context_options[option]

        # Check instance attributes
        value = getattr(self, option, None)
        if value is not None:
            return value

        # Fall back to Django settings
        return getattr(settings, f"COUNTRIES_{option.upper()}")

    @property
    def countries(self) -> Dict[str, "CountryName"]:
        """
        Return the a dictionary of countries, modified by any overriding
        options.

        The result is cached so future lookups are less work intensive.
        When context overrides 'only', we skip the cache to ensure correct results.
        """
        # Check if context overrides 'only' - if so, build fresh without caching
        context_options = getattr(_countries_context, "options", None)
        context_has_only = context_options and "only" in context_options

        if context_has_only:
            # Build countries dict without caching when context overrides 'only'
            return self._build_countries_dict()

        if not hasattr(self, "_countries"):
            self._countries = self._build_countries_dict()
        return self._countries

    def _build_countries_dict(self) -> Dict[str, "CountryName"]:
        """
        Build the countries dictionary based on current options.
        This is called by the countries property and may be cached or not
        depending on whether context is active.
        """
        only: Iterable[Union[str, Tuple[str, StrPromise]]] = self.get_option("only")
        only_choices = True
        # Originally used ``only`` as a dict, still supported.
        if only and not isinstance(only, dict):
            for item in only:
                if isinstance(item, str):
                    only_choices = False
                    break

        if not hasattr(self, "_shadowed_names"):
            self._shadowed_names: Dict[str, List[StrPromise]] = {}

        result_countries: Dict[str, CountryName]

        if only and only_choices:
            result_countries = dict(only)  # type: ignore
        else:
            # Local import so that countries aren't loaded into memory
            # until first used.
            from django_countries.data import COUNTRIES

            countries_dict = dict(COUNTRIES)
            if only:
                result_countries = {}
                for item in only:
                    if isinstance(item, str):
                        result_countries[item] = countries_dict[item]
                    else:
                        key, value = item
                        result_countries[key] = value
            else:
                result_countries = countries_dict.copy()  # type: ignore

            if self.get_option("common_names"):
                for code, name in self.COMMON_NAMES.items():
                    if code in result_countries:
                        result_countries[code] = name

            override: Dict[str, Union[CountryName, None]] = self.get_option("override")
            if override:
                _countries = cast(
                    "Dict[str, Union[CountryName, None]]", result_countries.copy()
                )
                for code, override_value in override.items():
                    if override_value is None:
                        # Remove the country
                        _countries[code] = None
                    elif isinstance(override_value, dict):
                        # Check if the dict has name/names
                        if (
                            "name" not in override_value
                            and "names" not in override_value
                        ):
                            # Merge with existing country data
                            existing = _countries.get(code)
                            if existing and isinstance(existing, dict):
                                # Merge the dicts
                                merged = existing.copy()  # type: ignore
                                merged.update(override_value)  # type: ignore
                                _countries[code] = merged  # type: ignore
                            elif existing:
                                # Convert existing string to dict with name
                                merged = {"name": existing}  # type: ignore
                                merged.update(override_value)  # type: ignore
                                _countries[code] = merged  # type: ignore
                            else:
                                # New country with only metadata, no name
                                _countries[code] = override_value
                        else:
                            # Full replacement with new name
                            _countries[code] = override_value
                    else:
                        # String override
                        _countries[code] = override_value
                result_countries = {  # type: ignore[misc]
                    code: name for code, name in _countries.items() if name is not None
                }

            if self.get_option("common_names"):
                for code in self.COMMON_NAMES:
                    if code in result_countries and code not in override:
                        self._shadowed_names[code] = [countries_dict[code]]
            for code, names in self.OLD_NAMES.items():
                if code in result_countries and code not in override:
                    country_shadowed = self._shadowed_names.setdefault(code, [])
                    country_shadowed.extend(names)

        self.countries_first = []
        first: List[str] = self.get_option("first") or []
        for code in first:
            # Just uppercase the code - don't use alpha2() to avoid recursion
            code_upper = force_str(code).upper()
            if code_upper in result_countries:
                self.countries_first.append(code_upper)

        return result_countries

    @countries.deleter  # type: ignore[no-redef,attr-defined]
    def countries(self):
        """
        Reset the countries cache in case for some crazy reason the settings or
        internal options change. But surely no one is crazy enough to do that,
        right?
        """
        if hasattr(self, "_countries"):
            del self._countries
        if hasattr(self, "_alt_codes"):
            del self._alt_codes
        if hasattr(self, "_ioc_codes"):
            del self._ioc_codes
        if hasattr(self, "_flag_urls"):
            del self._flag_urls
        if hasattr(self, "_shadowed_names"):
            del self._shadowed_names
        if hasattr(self, "_iter_cache"):
            del self._iter_cache

    @property
    def alt_codes(self) -> Dict[str, AltCodes]:
        if not hasattr(self, "_alt_codes"):
            # Again, local import so data is not loaded unless it's needed.
            from django_countries.data import ALT_CODES

            self._alt_codes = ALT_CODES  # type: ignore
            altered = False
            for code, country in self.countries.items():
                if isinstance(country, dict) and (
                    "alpha3" in country or "numeric" in country
                ):
                    if not altered:
                        self._alt_codes = self._alt_codes.copy()
                        altered = True
                    alpha3, numeric = self._alt_codes.get(code, ("", None))
                    if "alpha3" in country:
                        alpha3 = country["alpha3"]
                    if "numeric" in country:
                        numeric = country["numeric"]
                    self._alt_codes[code] = AltCodes(alpha3, numeric)
        return self._alt_codes

    @property
    def ioc_codes(self) -> Dict[str, str]:
        if not hasattr(self, "_ioc_codes"):
            from django_countries.ioc_data import ISO_TO_IOC

            self._ioc_codes = ISO_TO_IOC
            altered = False
            for code, country in self.countries.items():
                if isinstance(country, dict) and "ioc_code" in country:
                    if not altered:
                        self._ioc_codes = self._ioc_codes.copy()
                        altered = True
                    self._ioc_codes[code] = country["ioc_code"]
        return self._ioc_codes

    @property
    def flag_urls(self) -> Dict[str, str]:
        if not hasattr(self, "_flag_urls"):
            self._flag_urls: Dict[str, str] = {}
            for code, country in self.countries.items():
                if isinstance(country, dict) and "flag_url" in country:
                    self._flag_urls[code] = country["flag_url"]
        return self._flag_urls

    @property
    def shadowed_names(self):
        if not getattr(self, "_shadowed_names", False):
            # Getting countries populates shadowed names.
            self.countries  # noqa: B018
        return self._shadowed_names

    def translate_code(self, code: str, ignore_first: Optional[List[str]] = None):
        """
        Return translated countries for a country code.
        """
        country = self.countries[code]
        if isinstance(country, dict):
            names = country["names"] if "names" in country else [country["name"]]
        else:
            names = [country]
        if ignore_first and code in ignore_first:
            names = names[1:]
        for name in names:
            yield self.translate_pair(code, name)

    def translate_pair(self, code: str, name: Optional["CountryName"] = None):
        """
        Force a country to the current activated translation.

        :returns: ``CountryTuple(code, translated_country_name)`` namedtuple
        """
        if name is None:
            name = self.countries[code]
        if isinstance(name, dict):
            if "names" in name:
                fallback_names: List[StrPromise] = name["names"][1:]
                name = name["names"][0]
            else:
                fallback_names = []
                name = name["name"]
        else:
            fallback_names = self.shadowed_names.get(code, [])
        if fallback_names:
            with no_translation_fallback():
                country_name = force_str(name)
                # Check if there's an older translation available if there's no
                # translation for the newest name.
                if not country_name:
                    for fallback_name in fallback_names:
                        fallback_name_str = force_str(fallback_name)
                        if fallback_name_str:
                            country_name = fallback_name_str
                            break
            if not country_name:
                # Use the translation's fallback country name.
                country_name = force_str(name)
        else:
            country_name = force_str(name)
        return CountryTuple(code, country_name)

    def __call__(self):
        """
        Make Countries callable to support Django 5.0+ lazy callable choices.
        Returns self to enable deferred evaluation while maintaining caching.
        """
        return self

    def __iter__(self):
        """
        Iterate through countries, sorted by name.

        Each country record consists of a namedtuple of the two letter
        ISO3166-1 country ``code`` and short ``name``.

        The sorting happens based on the thread's current translation.

        Countries that are in ``settings.COUNTRIES_FIRST`` will be
        displayed before any sorted countries (in the order provided),
        and are only repeated in the sorted list if
        ``settings.COUNTRIES_FIRST_REPEAT`` is ``True``.

        The first countries can be separated from the sorted list by the
        value provided in ``settings.COUNTRIES_FIRST_BREAK``.

        Results are cached per language to avoid expensive re-translation
        and re-sorting on every iteration (issue #454).

        The cache key also includes the resolved first countries to ensure
        different country orderings get different cache entries.
        """
        # Get current language and resolved first countries for cache key
        language = get_language()
        resolved_first = tuple(self._resolve_first_countries())

        # Include all context options in cache key to ensure correct caching
        # when context overrides settings
        context_options = getattr(_countries_context, "options", None)
        if context_options:
            # Convert unhashable types to hashable for cache key
            hashable_options = {}
            for key, value in context_options.items():
                if isinstance(value, list):
                    hashable_options[key] = tuple(value)
                elif isinstance(value, dict):
                    # Convert dict to tuple of sorted items
                    hashable_options[key] = tuple(sorted(value.items()))
                else:
                    hashable_options[key] = value
            context_key = tuple(sorted(hashable_options.items()))
        else:
            context_key = ()

        cache_key = (language, resolved_first, context_key)

        # Initialize cache if needed
        if not hasattr(self, "_iter_cache"):
            self._iter_cache: Dict[
                Tuple[Optional[str], Tuple[str, ...], Tuple], List[CountryTuple]
            ] = {}

        # Return cached results if available for this language + first countries
        if cache_key in self._iter_cache:
            yield from self._iter_cache[cache_key]
            return

        # Build the country list (original logic)
        results = []

        # Initializes countries_first, so needs to happen first.
        countries = self.countries

        # Get the dynamically resolved list of countries to show first
        # (based on language, context, or static setting)
        first_codes = []
        for code in resolved_first:
            code = self.alpha2(code)
            if code in self._countries:
                first_codes.append(code)

        # Yield countries that should be displayed first.
        countries_first = (self.translate_pair(code) for code in first_codes)

        if self.get_option("first_sort"):
            countries_first = sorted(countries_first, key=sort_key)

        results.extend(countries_first)

        if first_codes:
            first_break = self.get_option("first_break")
            if first_break:
                results.append(CountryTuple("", force_str(first_break)))

        # Force translation before sorting.
        ignore_first = None if self.get_option("first_repeat") else first_codes
        countries_translated = tuple(
            itertools.chain.from_iterable(
                self.translate_code(code, ignore_first) for code in countries
            )
        )

        # Add sorted country list.
        results.extend(sorted(countries_translated, key=sort_key))

        # Cache and return results
        self._iter_cache[cache_key] = results
        yield from results

    def alpha2(self, code: "CountryCode") -> str:
        """
        Return the normalized country code when passed any type of ISO 3166-1
        country code.

        Overridden countries objects may actually have country codes that are
        not two characters (for example, "GB-WLS"), so the returned length of
        the code is not guaranteed.

        If no match is found, returns an empty string.
        """
        code_str = force_str(code).upper()
        # Check if the code exists directly in countries first, before trying
        # to resolve it as an alternative code (alpha3/numeric). This allows
        # custom country codes in COUNTRIES_OVERRIDE to work correctly, even
        # if they match the format of alternative codes (issue #474).
        if code_str in self.countries:
            return code_str

        find_index: Optional[int]
        find_value: Union[str, int, None]

        if code_str.isdigit():
            find_index = 1
            find_value = int(code_str)
        elif len(code_str) == 3:
            find_index = 0
            find_value = code_str
        else:
            find_index = None
            find_value = None
        if find_index is not None:
            code_str = ""
            for alpha2, alt_codes in self.alt_codes.items():
                if alt_codes[find_index] == find_value:
                    code_str = alpha2
                    break
        if code_str in self.countries:
            return code_str
        return ""

    def name(self, code: "CountryCode") -> str:
        """
        Return the name of a country, based on the code.

        If no match is found, returns an empty string.
        """
        alpha2 = self.alpha2(code)
        if alpha2 not in self.countries:
            return ""
        return self.translate_pair(alpha2)[1]

    @overload
    def by_name(
        self,
        country: str,
        *,
        regex: Literal[False] = False,
        language: str = "en",
        insensitive: bool = True,
    ) -> str: ...

    @overload
    def by_name(
        self,
        country: str,
        *,
        regex: Literal[True],
        language: str = "en",
        insensitive: bool = True,
    ) -> Set[str]: ...

    def by_name(
        self,
        country: str,
        *,
        regex: bool = False,
        language: str = "en",
        insensitive: bool = True,
    ) -> Union[str, Set[str]]:
        """
        Fetch a country's ISO3166-1 two letter country code from its name.

        An optional language parameter is also available. Warning: This depends
        on the quality of the available translations.

        If no match is found, returns an empty string.

        If ``regex`` is set to True, then rather than returning a string
        containing the matching country code or an empty string, a set of
        matching country codes is returned.

        If ``insensitive`` is set to False (True by default), then the search
        will be case sensitive.

        ..warning:: Be cautious about relying on this returning a country code
            (especially with any hard-coded string) since the ISO names of
            countries may change over time.
        """
        code_list = set()
        if regex:
            re_match = re.compile(country, insensitive and re.IGNORECASE)
        elif insensitive:
            country = country.lower()
        with override(language):
            for code, check_country in self.countries.items():
                if isinstance(check_country, dict):
                    if "names" in check_country:
                        check_names: List[StrPromise] = check_country["names"]
                    else:
                        check_names = [check_country["name"]]
                else:
                    check_names = [check_country]
                for name in check_names:
                    if regex:
                        if re_match.search(str(name)):
                            code_list.add(code)
                    else:
                        if insensitive:
                            if country == name.lower():
                                return code
                        else:
                            if country == name:
                                return code
                if code in self.shadowed_names:
                    for shadowed_name in self.shadowed_names[code]:
                        if regex:
                            if re_match.search(str(shadowed_name)):
                                code_list.add(code)
                        else:
                            if insensitive:
                                shadowed_name = shadowed_name.lower()
                            if country == shadowed_name:
                                return code
        if regex:
            return code_list
        return ""

    def alpha3(self, code: "CountryCode") -> str:
        """
        Return the ISO 3166-1 three letter country code matching the provided
        country code.

        If no match is found, returns an empty string.
        """
        alpha2 = self.alpha2(code)
        try:
            alpha3 = self.alt_codes[alpha2][0]
        except KeyError:
            alpha3 = ""
        return alpha3 or ""

    @overload
    def numeric(self, code: Union[str, int, None]) -> Optional[int]: ...

    @overload
    def numeric(self, code: Union[str, int, None], padded=True) -> Optional[str]: ...

    def numeric(self, code: Union[str, int, None], padded: bool = False):
        """
        Return the ISO 3166-1 numeric country code matching the provided
        country code.

        If no match is found, returns ``None``.

        :param padded: Pass ``True`` to return a 0-padded three character
            string, otherwise an integer will be returned.
        """
        alpha2 = self.alpha2(code)
        try:
            num = self.alt_codes[alpha2][1]
        except KeyError:
            num = None
        if num is None:
            return None
        if padded:
            return f"{num:03d}"
        return num

    def ioc_code(self, code: "CountryCode") -> str:
        """
        Return the International Olympic Committee three letter code matching
        the provided ISO 3166-1 country code.

        If no match is found, returns an empty string.
        """
        alpha2 = self.alpha2(code)
        return self.ioc_codes.get(alpha2, "")

    def flag_url(self, code: "CountryCode") -> str:
        """
        Return the custom flag URL for the provided country code.

        If no custom flag URL is found, returns an empty string.
        """
        alpha2 = self.alpha2(code)
        return self.flag_urls.get(alpha2, "")

    def __len__(self):
        """
        len() used by several third party applications to calculate the length
        of choices. This will solve a bug related to generating fixtures.
        """
        count = len(self.countries)
        # Add first countries, and the break if necessary.
        resolved_first = self._resolve_first_countries()
        # Normalize country codes
        first_codes = []
        for code in resolved_first:
            code = self.alpha2(code)
            if code in self._countries:
                first_codes.append(code)
        count += len(first_codes)
        if first_codes and self.get_option("first_break"):
            count += 1
        return count

    def __bool__(self):
        return bool(self.countries)

    def __contains__(self, code):
        """
        Check to see if the countries contains the given code.
        """
        return code in self.countries

    def __getitem__(self, index):
        """
        Some applications expect to be able to access members of the field
        choices by index.
        """
        try:
            return next(itertools.islice(self.__iter__(), index, index + 1))
        except TypeError:
            return list(
                itertools.islice(self.__iter__(), index.start, index.stop, index.step)
            )


countries = Countries()
