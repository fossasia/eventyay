from typing import Any, Dict, Optional

import dateutil.parser
import decimal
import json
from datetime import date, datetime, time
from django.core.cache import cache
from django.core.files import File
from django.core.files.storage import default_storage
from django.db.models import Model
from functools import cached_property

from hierarkey.models import Hierarkey


class HierarkeyProxy:
    """
    If you add a hierarkey storage to a model, the model will get a new attribute (e.g. ``settings``) containing
    a key-value store that is managed by this class.

    This class allows access to settings via attribute access, item access or using the documented methods.
    You should not instantiate this class yourself.
    """

    @classmethod
    def _new(cls, obj: Model, hierarkey: Hierarkey, cache_namespace: str, parent: Optional[Model] = None,
             type: type = None):
        o = HierarkeyProxy()
        o._obj = obj
        o._h = hierarkey
        o._cache_namespace = cache_namespace
        o._parent = parent
        o._cached_obj = None
        o._type = type
        return o

    @property
    def _objects(self):
        """
        Returns a model manager (or related object manager) giving access to the raw objects backing this
        storage level.
        """
        return getattr(self._obj, '_%s_objects' % self._h.attribute_name)

    def _cache(self) -> Dict[str, Any]:
        if self._cached_obj is None:
            self._cached_obj = cache.get_or_set(
                'hierarkey_{}_{}'.format(self._cache_namespace, self._obj.pk),
                lambda: {s.key: s.value for s in self._objects.all()},
                timeout=1800
            )
        return self._cached_obj

    def flush(self) -> None:
        """
        Discards both the state within this object as well as the cache in Django's cache backend.
        """
        self._cached_obj = None
        self._flush_external_cache()

    def _flush_external_cache(self):
        cache.delete('hierarkey_{}_{}'.format(self._cache_namespace, self._obj.pk))

    def freeze(self) -> dict:
        """
        Returns a dictionary of all settings set for this object, including
        any values of its parents or hardcoded defaults.
        """
        settings = {}
        for key, v in self._h.defaults.items():
            settings[key] = self._unserialize(v.value, v.type)
        if self._parent:
            settings.update(getattr(self._parent, self._h.attribute_name).freeze())
        for key in self._cache():
            settings[key] = self.get(key)
        return settings

    def _unserialize(self, value: str, as_type: type, binary_file=False) -> Any:
        if as_type is None and value is not None and value.startswith('file://'):
            as_type = File

        if as_type is not None and isinstance(value, as_type):
            return value
        elif value is None:
            return None
        elif as_type == int or as_type == float or as_type == decimal.Decimal:
            return as_type(value)
        elif as_type == dict or as_type == list:
            return json.loads(value)
        elif as_type == bool or value in ('True', 'False'):
            return value == 'True'
        elif as_type == File:
            try:
                fi = default_storage.open(value[7:], 'rb' if binary_file else 'r')
                fi.url = default_storage.url(value[7:])
                return fi
            except OSError:
                return False
        elif as_type == datetime:
            return dateutil.parser.parse(value)
        elif as_type == date:
            return dateutil.parser.parse(value).date()
        elif as_type == time:
            return dateutil.parser.parse(value).time()
        elif as_type is not None:
            for t in self._h.types:
                if issubclass(as_type, t.type):
                    return t.unserialize(value)

        if as_type is not None and issubclass(as_type, Model):
            return as_type.objects.get(pk=value)

        return value

    def _serialize(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        elif isinstance(value, int) or isinstance(value, float) \
                or isinstance(value, bool) or isinstance(value, decimal.Decimal):
            return str(value)
        elif isinstance(value, list) or isinstance(value, dict):
            return json.dumps(value)
        elif isinstance(value, datetime) or isinstance(value, date) or isinstance(value, time):
            return value.isoformat()
        elif isinstance(value, Model):
            return value.pk
        elif isinstance(value, File):
            return 'file://' + value.name
        else:
            for t in self._h.types:
                if isinstance(value, t.type):
                    return t.serialize(value)

        raise TypeError('Unable to serialize %s into a setting.' % str(type(value)))

    def get(self, key: str, default=None, as_type: type = None, binary_file: bool = False):
        """
        Get a setting specified by ``key``. Normally, settings are strings, but
        if you put non-strings into the settings object, you can request deserialization
        by specifying ``as_type``. If the key does not have a harcdoded default type,
        omitting ``as_type`` always will get you a string.

        If the setting with the specified name does not exist on this object, any parent object
        up to the global settings layer (if configured) will be queried. If still no value is
        found, a default value set in ths source code will be returned if one exists.
        If not, the value of the ``default`` argument of this method will be returned instead.

        If you receive a ``File`` object, it will already be opened. You can specify the ``binary_file``
        flag to indicate that it should be opened in binary mode.
        """
        if as_type is None:
            as_type = self._h.get_declared_type(key)

        if key in self._cache():
            value = self._cache()[key]
        else:
            value = None
            if self._parent:
                value = getattr(self._parent, self._h.attribute_name).get(key, as_type=str)
            if value is None and key in self._h.defaults:
                value = self._h.defaults[key].value
            if value is None and default is not None:
                value = default

        return self._unserialize(value, as_type, binary_file=binary_file)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __getattr__(self, key: str) -> Any:
        if key.startswith('_'):  # pragma: no cover
            return super().__getattribute__(key)
        return self.get(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith('_'):
            return super().__setattr__(key, value)
        self.set(key, value)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    @cached_property
    def __is_global(self):
        return "object" not in [f.name for f in self._type._meta.fields]

    def set(self, key: str, value: Any) -> None:
        """
        Stores a setting in the database and connects it to its object.

        The write to the database is performed immediately and the cache in the cache backend is flushed.
        The cache within this object will be updated correctly.
        """
        serialized_value = self._serialize(value)

        key_attributes = {
            "key": key,
        }
        if not self.__is_global:
            key_attributes["object"] = self._obj
        s, created = self._type.objects.update_or_create(
            **key_attributes,
            defaults={
                "value": serialized_value,
            }
        )
        self._cache()[key] = s.value
        self._flush_external_cache()

    def __delattr__(self, key: str) -> None:
        if key.startswith('_'):  # pragma: no cover
            return super().__delattr__(key)
        self.delete(key)

    def __delitem__(self, key: str) -> None:
        self.delete(key)

    def delete(self, key: str) -> None:
        """
        Deletes a setting from this object's storage.

        The write to the database is performed immediately and the cache in the cache backend is flushed.
        The cache within this object will be updated correctly.
        """
        key_attributes = {
            "key": key,
        }
        if not self.__is_global:
            key_attributes["object"] = self._obj

        self._type.objects.filter(**key_attributes).delete()

        if key in self._cache():
            del self._cache()[key]

        self._flush_external_cache()
