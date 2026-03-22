"""
Type stubs for django_countries.fields

This stub file provides enhanced type hints for better IDE support.
The actual implementation is in fields.py.
"""

from typing import Any, Iterable, Literal, overload

from django.db import models
from typing_extensions import Self, TypeAlias

from django_countries import Countries

# Re-export countries singleton from fields module
countries: Countries

# Type aliases for clarity
_CountryCode: TypeAlias = str
_FlagURL: TypeAlias = str

class Country:
    code: _CountryCode | None
    flag_url: _FlagURL | None

    def __init__(
        self,
        code: _CountryCode | None,
        flag_url: _FlagURL | None = None,
        str_attr: str = "code",
        custom_countries: Countries | None = None,
    ) -> None: ...
    def __str__(self) -> str: ...
    def __bool__(self) -> bool: ...
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
    @property
    def name(self) -> str | None: ...
    @property
    def alpha3(self) -> str | None: ...
    @property
    def numeric(self) -> str | None: ...
    @property
    def ioc_code(self) -> str | None: ...
    @property
    def unicode_flag(self) -> str: ...
    @property
    def flag(self) -> _FlagURL: ...

class MultipleCountriesDescriptor:
    """List-like wrapper for multiple countries."""

    def __init__(self, countries_iter: Iterable[Country]) -> None: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...
    def __iter__(self) -> Any: ...
    def __getitem__(self, index: int) -> Country: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...
    def __eq__(self, other: object) -> bool: ...

class CountryDescriptor:
    """
    Descriptor that returns Country objects or MultipleCountriesDescriptor.

    Return type depends on field configuration:
    - Single field (multiple=False): Returns Country (code may be None)
    - Multiple field (multiple=True, null=False):
      Returns MultipleCountriesDescriptor
    - Multiple field (multiple=True, null=True):
      Returns MultipleCountriesDescriptor | None
    """

    field: CountryField

    def __init__(self, field: CountryField) -> None: ...

    # When accessed on class, returns descriptor itself
    @overload
    def __get__(self, instance: None, owner: type) -> Self: ...

    # When accessed on instance, returns based on field config
    @overload
    def __get__(
        self, instance: object, owner: type
    ) -> Country | MultipleCountriesDescriptor | None: ...
    def __set__(self, instance: Any, value: Any) -> None: ...

class CountryField(models.CharField):
    """
    A Django field for storing country codes.

    Type inference notes:
    - When multiple=False: Instance access returns Country
    - When multiple=True, null=False:
      Instance access returns MultipleCountriesDescriptor
    - When multiple=True, null=True:
      Instance access returns MultipleCountriesDescriptor | None

    The descriptor is CountryDescriptor,
    accessible via Model.__class__.<field_name>
    """

    descriptor_class: type[CountryDescriptor]
    multiple: bool

    # Overload for single, non-nullable (most common)
    @overload
    def __init__(
        self,
        *,
        multiple: Literal[False] = False,
        null: Literal[False] = False,
        blank: bool = False,
        countries: type[Countries] | None = None,
        countries_flag_url: str | None = None,
        countries_str_attr: str = "code",
        blank_label: str | None = None,
        **kwargs: Any,
    ) -> None: ...

    # Overload for single, nullable
    @overload
    def __init__(
        self,
        *,
        multiple: Literal[False] = False,
        null: Literal[True],
        blank: bool = True,
        countries: type[Countries] | None = None,
        countries_flag_url: str | None = None,
        countries_str_attr: str = "code",
        blank_label: str | None = None,
        **kwargs: Any,
    ) -> None: ...

    # Overload for multiple, non-nullable
    @overload
    def __init__(
        self,
        *,
        multiple: Literal[True],
        null: Literal[False] = False,
        blank: bool = False,
        multiple_sort: bool = True,
        multiple_unique: bool = True,
        countries: type[Countries] | None = None,
        countries_flag_url: str | None = None,
        countries_str_attr: str = "code",
        **kwargs: Any,
    ) -> None: ...

    # Overload for multiple, nullable (new in PR #453)
    @overload
    def __init__(
        self,
        *,
        multiple: Literal[True],
        null: Literal[True],
        blank: bool = True,
        multiple_sort: bool = True,
        multiple_unique: bool = True,
        countries: type[Countries] | None = None,
        countries_flag_url: str | None = None,
        countries_str_attr: str = "code",
        **kwargs: Any,
    ) -> None: ...
