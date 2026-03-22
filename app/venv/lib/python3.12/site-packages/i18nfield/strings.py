from typing import Dict, Optional, Union

import json
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext, override


class LazyI18nString:
    """
    This represents an internationalized string that is/was/will be stored in the database.
    """

    def __init__(self, data: Optional[Union[str, Dict[str, str]]]):
        """
        Creates a new i18n-aware string.

        :param data: If this is a dictionary, it is expected to map language codes to translations.
            If this is a string that can be parsed as JSON, it will be parsed and used as such a dictionary.
            If this is anything else, it will be cast to a string and used for all languages.
        """
        self.data = data
        if isinstance(self.data, str) and self.data is not None:
            try:
                j = json.loads(self.data)
            except ValueError:
                pass
            else:
                self.data = j

    def __str__(self) -> str:
        """
        Evaluate the given string with respect to the currently active locale.

        If no string is available in the currently active language, this will give you
        the string in the system's default language. If this is unavailable as well, it
        will give you the string in the first language available.
        """
        return self.localize(translation.get_language() or settings.LANGUAGE_CODE)

    def __bool__(self) -> bool:
        if not self.data:
            return False
        if isinstance(self.data, dict):
            return any(self.data.values())
        return True

    def localize(self, lng: str) -> str:
        """
        Evaluate the given string with respect to the locale defined by ``lng``.

        If no string is available in the currently active language, this will give you
        the string in the system's default language. If this is unavailable as well, it
        will give you the string in the first language available.

        :param lng: A locale code, e.g. ``de``. If you specify a code including a country
            or region like ``de-AT``, exact matches will be used preferably, but if only
            a ``de`` or ``de-AT`` translation exists, this might be returned as well.
        """
        if self.data is None:
            return ""

        if isinstance(self.data, dict):
            firstpart = lng.split('-')[0]
            similar = [
                loc for loc in self.data.keys()
                if (loc.startswith(firstpart + "-") or firstpart == loc) and loc != lng
            ]
            if self.data.get(lng):
                return self.data[lng]
            elif self.data.get(firstpart):
                return self.data[firstpart]
            elif similar and any([self.data.get(s) for s in similar]):
                for s in similar:
                    if self.data.get(s):
                        return self.data.get(s)
            elif self.data.get(settings.LANGUAGE_CODE):
                return self.data[settings.LANGUAGE_CODE]
            else:
                filled = [f for f in self.data.values() if f]
                if filled:
                    return filled[0]
                else:
                    return ""
        else:
            with override(lng):
                return str(self.data)

    def map(self, f):
        """
        Apply a transformation function f to all translations.
        """
        self.data = {k: f(v) for k, v in self.data.items()}

    def __repr__(self) -> str:  # NOQA
        return '<LazyI18nString: %s>' % repr(self.data)

    def __lt__(self, other) -> bool:  # NOQA
        return str(self) < str(other)

    def __format__(self, format_spec):
        return self.__str__()

    def __eq__(self, other):
        if other is None:
            return False
        if hasattr(other, 'data'):
            return self.data == other.data
        return self.data == other

    class LazyGettextProxy:
        def __init__(self, lazygettext):
            self.lazygettext = lazygettext

        def __getitem__(self, item):
            with override(item):
                return str(gettext(self.lazygettext))

        def __contains__(self, item):
            return True

        def __str__(self):
            return str(gettext(self.lazygettext))

        def __repr__(self):  # NOQA
            return '<LazyGettextProxy: %s>' % repr(self.lazygettext)

    @classmethod
    def from_gettext(cls, lazygettext) -> 'LazyI18nString':
        result = LazyI18nString({})
        result.data = cls.LazyGettextProxy(lazygettext)
        return result
