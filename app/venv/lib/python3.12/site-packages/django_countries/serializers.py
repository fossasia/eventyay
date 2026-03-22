from typing import Any, Dict

from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers

from . import fields, serializer_fields


class CountryFieldMixin:
    # List of country-specific field options that should not be passed to ListField
    _country_field_options = [
        "country_dict",
        "name_only",
    ]

    def get_extra_kwargs(self):
        """
        Override to filter out country-specific options for multiple CountryFields.

        For multiple CountryFields (which become ListField), we need to prevent
        country-specific options from being applied to the ListField itself,
        as they should only apply to the child CountryField.
        """
        extra_kwargs = super().get_extra_kwargs()  # type: ignore

        # Filter country-specific options for multiple CountryFields
        for field_name, field_extra_kwargs in extra_kwargs.items():
            # Check if this is a multiple CountryField
            model = getattr(self.Meta, "model", None)
            if model:
                try:
                    model_field = model._meta.get_field(field_name)
                    is_country_field = isinstance(model_field, fields.CountryField)
                    if is_country_field and model_field.multiple:
                        # Remove country-specific options so they don't get applied
                        # to ListField
                        for option in self._country_field_options:
                            field_extra_kwargs.pop(option, None)
                except FieldDoesNotExist:
                    # Field doesn't exist on model, skip it
                    pass

        return extra_kwargs

    def build_standard_field(self, field_name, model_field):
        field_kwargs: Dict[str, Any]
        field_class, field_kwargs = super().build_standard_field(  # type: ignore
            field_name, model_field
        )
        if (
            # Only deal with CountryFields.
            not isinstance(model_field, fields.CountryField)
            # Some other mixin has changed the field class already!
            or field_class is not serializers.ChoiceField
        ):
            return field_class, field_kwargs

        # Extract CountryField-specific options from extra_kwargs
        extra_kwargs = getattr(getattr(self, "Meta", None), "extra_kwargs", {})
        field_extra_kwargs = extra_kwargs.get(field_name, {})

        # Extract CountryField output customization options
        country_field_options = {}
        for option in self._country_field_options:
            if option in field_extra_kwargs:
                country_field_options[option] = field_extra_kwargs[option]

        field_kwargs["countries"] = model_field.countries
        del field_kwargs["choices"]
        if not model_field.multiple:
            # For single country fields, add the country_field_options
            field_kwargs.update(country_field_options)
            field_class = serializer_fields.CountryField
        else:
            # For multiple country fields, only pass country_field_options to
            # the child field
            child_kwargs = field_kwargs.copy()
            child_kwargs.update(country_field_options)
            field_class = serializers.ListField
            child_field = serializer_fields.CountryField(**child_kwargs)
            field_kwargs = {"child": child_field}
            if "max_length" in serializers.ListField.default_error_messages:
                # Added in DRF 3.5.4
                field_kwargs["max_length"] = len(child_field.countries)
        return field_class, field_kwargs
