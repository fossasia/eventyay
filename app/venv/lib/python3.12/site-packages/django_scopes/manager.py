from django.db import models

from .exceptions import ScopeError
from .state import get_scope


class DisabledQuerySet(models.QuerySet):

    def __init__(self, *args, **kwargs):
        self.missing_scopes = kwargs.pop('missing_scopes', None)
        super().__init__(*args, **kwargs)

    def error(self, *args, **kwargs):
        raise ScopeError("A scope on dimension(s) {} needs to be active for this query.".format(
            ', '.join(self.missing_scopes)
        ))

    def _clone(self):
        c = super()._clone()
        c.missing_scopes = self.missing_scopes
        return c

    def none(self):
        c = models.QuerySet(model=self.model, query=self.query.chain(), using=self._db, hints=self._hints)
        c._sticky_filter = self._sticky_filter
        c._for_write = self._for_write
        c._prefetch_related_lookups = self._prefetch_related_lookups[:]
        c._known_related_objects = self._known_related_objects
        c._iterable_class = self._iterable_class
        c._fields = self._fields
        return c.none()

    # We protect disable everything except for .using(), .none() and .create()
    __bool__ = error
    __getitem__ = error
    __iter__ = error
    __len__ = error
    __erpr__ = error
    all = error
    aggregate = error
    annotate = error
    count = error
    earliest = error
    complex_filter = error
    select_for_update = error
    filter = error
    first = error
    get = error
    get_or_create = error
    update_or_create = error
    delete = error
    dates = error
    datetimes = error
    iterator = error
    last = error
    latest = error
    only = error
    order_by = error
    reverse = error
    union = error
    update = error
    raw = error
    values = error
    values_list = error


def ScopedManager(_manager_class=models.Manager, **scopes):
    required_scopes = set(scopes.keys())

    class Manager(_manager_class):
        def __init__(self):
            super().__init__()

        def get_queryset(self):
            current_scope = get_scope()
            if not current_scope.get('_enabled', True):
                return super().get_queryset()
            missing_scopes = required_scopes - set(current_scope.keys())
            if missing_scopes:
                return DisabledQuerySet(self.model, using=self._db, missing_scopes=missing_scopes)
            else:
                filter_kwargs = {}
                for dimension in required_scopes:
                    current_value = current_scope[dimension]
                    if isinstance(current_value, (list, tuple)):
                        filter_kwargs[scopes[dimension] + '__in'] = current_value
                    elif current_value is not None:
                        filter_kwargs[scopes[dimension]] = current_value
                return super().get_queryset().filter(**filter_kwargs)

        def all(self):
            a = super().all()
            if isinstance(a, DisabledQuerySet):
                a = a.all()
            return a

    return Manager()
