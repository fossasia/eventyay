from django.db import models

from .gh_regions import REGIONS


class GHRegionField(models.CharField):
    """
        A model field that provides an option to select
        a region from the list of all Ghana regions.
        .. versionadded:: 4.0
    """

    def __init__(self, *args, **kwargs):
        kwargs['choices'] = REGIONS
        kwargs['max_length'] = 13
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        del kwargs['choices']
        return name, path, args, kwargs
