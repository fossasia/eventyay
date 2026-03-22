from typing import Any, List

from django.utils.encoding import force_str
from django.utils.translation import get_language
from rest_framework import serializers

from django_countries import countries


class CountryField(serializers.ChoiceField):
    _DEFAULT_COUNTRY_DICT_KEYS = ("code", "name")
    _VALID_COUNTRY_DICT_KEYS = {
        "code",
        "name",
        "alpha3",
        "numeric",
        "unicode_flag",
        "ioc_code",
    }
    _KEY_SCHEMAS = {
        "code": {"type": "string", "minLength": 2, "maxLength": 2},
        "name": {"type": "string"},
        "alpha3": {"type": "string", "minLength": 3, "maxLength": 3},
        "numeric": {"type": "integer"},
        "unicode_flag": {"type": "string"},
        "ioc_code": {"type": "string"},
    }

    def __init__(self, *args, **kwargs):
        self.country_dict = kwargs.pop("country_dict", None)
        self.name_only = kwargs.pop("name_only", None)
        field_countries = kwargs.pop("countries", None)
        self.countries = field_countries or countries
        self.country_dict_keys = self._build_country_dict_keys()
        self.country_dict = bool(self.country_dict_keys)
        super().__init__(
            self.countries,  # type: ignore
            *args,
            **kwargs,
        )
        # Set up drf-spectacular annotation
        self._setup_spectacular_annotation()

    def to_representation(self, obj):
        code = self.countries.alpha2(obj)
        if not code:
            # Respect allow_null setting for empty values
            if self.allow_null:
                return None
            return ""
        if self.name_only:
            return force_str(self.countries.name(obj))
        if not self.country_dict:
            return code

        result = {}
        country_name = force_str(self.countries.name(obj))
        country_obj = None

        def get_country_obj():
            nonlocal country_obj
            if country_obj is None:
                from django_countries.fields import Country

                country_obj = Country(code, custom_countries=self.countries)
            return country_obj

        for key in self.country_dict_keys:
            if key == "code":
                result["code"] = code
            elif key == "name":
                result["name"] = country_name
            elif key == "alpha3":
                result["alpha3"] = get_country_obj().alpha3
            elif key == "numeric":
                result["numeric"] = get_country_obj().numeric
            elif key == "unicode_flag":
                result["unicode_flag"] = get_country_obj().unicode_flag
            elif key == "ioc_code":
                result["ioc_code"] = get_country_obj().ioc_code

        return result

    def to_internal_value(self, data: Any):
        if not self.allow_blank and data == "":
            self.fail("invalid_choice", input=data)

        if isinstance(data, dict):
            data = data.get("code")
        country = self.countries.alpha2(data)
        if data and not country:
            # Use current language for localized country name deserialization
            current_language = get_language() or "en"
            country = self.countries.by_name(force_str(data), language=current_language)
            # Fallback to English if not found in current language
            if not country and current_language != "en":
                country = self.countries.by_name(force_str(data), language="en")
            if not country:
                self.fail("invalid_choice", input=data)
        return country

    def _get_country_dict_schema(self):
        """Return schema for country_dict representation."""
        properties = {key: self._KEY_SCHEMAS[key] for key in self.country_dict_keys}
        required = list(self.country_dict_keys)
        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        if self.allow_null:
            schema = {"oneOf": [schema, {"type": "null"}]}
        return schema

    def _get_name_only_schema(self):
        """Return schema for name_only representation."""
        schema = {"type": "string"}
        if self.allow_null:
            schema = {"oneOf": [schema, {"type": "null"}]}
        return schema

    def _setup_spectacular_annotation(self):
        """
        Set up schema annotation for drf-spectacular.

        This sets the _spectacular_annotation attribute that drf-spectacular
        checks when generating OpenAPI schemas. When country_dict=True or
        name_only=True, we override the default ChoiceField enum schema
        with the appropriate schema for the actual representation.
        """
        if self.country_dict:
            schema = self._get_country_dict_schema()
            # Store as 'field' key like extend_schema_field decorator does
            self._spectacular_annotation = {"field": schema}
        elif self.name_only:
            schema = self._get_name_only_schema()
            self._spectacular_annotation = {"field": schema}
        # For standard code output, don't set annotation to allow
        # default ChoiceField enum handling

    def _build_country_dict_keys(self) -> List[str]:
        return self._normalize_country_dict_option(self.country_dict)

    def _normalize_country_dict_option(self, option) -> List[str]:
        if not option:
            return []
        if option is True:
            return list(self._DEFAULT_COUNTRY_DICT_KEYS)
        if isinstance(option, str):
            candidate = [option]
        else:
            try:
                candidate = list(option)  # type: ignore[arg-type]
            except TypeError as exc:
                raise TypeError(
                    "country_dict must be a boolean or an iterable of keys."
                ) from exc
        if not candidate:
            raise ValueError("country_dict iterable must include at least one key.")
        normalized: List[str] = []
        seen = set()
        for raw_key in candidate:
            if not isinstance(raw_key, str):
                raise TypeError("country_dict keys must be strings.")
            key = raw_key.strip().lower()
            if not key:
                raise ValueError("country_dict keys must be non-empty strings.")
            if key not in self._VALID_COUNTRY_DICT_KEYS:
                raise ValueError(
                    f"Unsupported country_dict key '{raw_key}'. "
                    f"Valid keys: {', '.join(sorted(self._VALID_COUNTRY_DICT_KEYS))}."
                )
            if key not in seen:
                normalized.append(key)
                seen.add(key)
        return normalized
