from django_filters import ChoiceFilter


class CountryFilter(ChoiceFilter):
    """
    ChoiceFilter that pre-populates choices with django-countries.

    Example:
        from django_countries.django_filters import CountryFilter

        class PersonFilter(FilterSet):
            country = CountryFilter(empty_label="Any country")
    """

    def __init__(self, *args, **kwargs):
        from django_countries import countries

        kwargs.setdefault("choices", countries)
        super().__init__(*args, **kwargs)
