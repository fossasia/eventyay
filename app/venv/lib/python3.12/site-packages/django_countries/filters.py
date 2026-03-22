import django
from django.contrib import admin
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _


class CountryFilter(admin.FieldListFilter):
    """
    A country filter for Django admin that only returns a list of countries
    related to the model.
    """

    title = _("Country")  # type: ignore

    def expected_parameters(self):
        if self.field.multiple:
            return [f"{self.field_path}__contains"]
        return [self.field_path]

    def choices(self, changelist):
        # Use __contains lookup for multiple country fields
        if self.field.multiple:
            field_name = f"{self.field_path}__contains"
        else:
            field_name = self.field_path

        value = self.used_parameters.get(field_name)
        # In Django 5.x, query parameters may come as lists
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        yield {
            "selected": value is None,
            "query_string": changelist.get_query_string({}, [field_name]),
            "display": _("All"),
        }
        for lookup, title in self.lookup_choices(changelist):
            selected = force_str(lookup) == value
            if django.VERSION >= (5, 0):
                selected = value is not None and selected
            yield {
                "selected": selected,
                "query_string": changelist.get_query_string({field_name: lookup}, []),
                "display": title,
            }

    def lookup_choices(self, changelist):
        qs = changelist.model._default_manager.all()
        values = (
            qs.distinct()
            .order_by(self.field_path)
            .values_list(self.field_path, flat=True)
        )

        # For multiple country fields, split comma-separated values
        codes = set()
        if self.field.multiple:
            for value in values:
                if value:  # Handle None/empty values
                    codes.update(
                        code.strip() for code in value.split(",") if code.strip()
                    )
        else:
            codes = set(values)

        for k, v in self.field.get_choices(include_blank=False):
            if k in codes:
                yield k, v
