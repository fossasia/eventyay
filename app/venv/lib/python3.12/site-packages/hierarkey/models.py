from typing import Any, Callable, Optional

import sys
from collections import namedtuple
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class BaseHierarkeyStoreModel(models.Model):
    key = models.CharField(max_length=255)
    value = models.TextField()

    def __repr__(self):
        return '<{}: "{}"{}>'.format(
            type(self).__name__,
            self.key,
            ' on object {}'.format(self.object_id) if hasattr(self, 'object_id') else '',
        )

    class Meta:
        abstract = True


HierarkeyDefault = namedtuple('HierarkeyDefault', ['value', 'type'])
HierarkeyType = namedtuple('HierarkeyType', ['type', 'serialize', 'unserialize'])


class Hierarkey:
    """
    The Hierarkey object represents one complete key-value store hierarchy. It can have one global and multiple
    object-level storages attached and holds default values as well as custom type serialization info.

    :param attribute_name: The name for the attribute on the model instances that will allow access to the
                           storage, e.g. ``settings``.
    """

    def __init__(self, attribute_name):
        self.attribute_name = attribute_name
        self.global_class = None
        self.defaults = {}
        self.types = []

    def _create_attrs(self, base_model: type, unique_together_) -> dict:
        class Meta:
            unique_together = unique_together_

        attrs = {
            'Meta': Meta,
            '__module__': base_model.__module__,
        }
        return attrs

    def _create_model(self, model_name: str, attrs: dict) -> type:
        return models.base.ModelBase(model_name, (BaseHierarkeyStoreModel,), attrs)

    def add_default(self, key: str, value: Optional[str], default_type: type = str) -> None:
        """
        Adds a default value and a default type for a key.

        :param key: Key
        :param value: *Serialized* default value, i.e. a string or ``None``.
        :param default_type: The type to deserialize values for this key to, defaults to ``str``.
        """
        self.defaults[key] = HierarkeyDefault(value, default_type)

    def get_declared_type(self, key: str) -> type:
        """
        Returns the type that is declared for a key using add_default.

        :param key: Key
        """
        return self.defaults[key].type if key in self.defaults else None

    def add_type(self, type: type, serialize: Callable[[Any], str], unserialize: Callable[[str], Any]) -> None:
        """
        Adds serialization support for a new type.

        :param type: The type to add support for.
        :param serialize: A callable that takes an object of type ``type`` and returns a string.
        :param unserialize: A callable that takes a string and returns an object of type ``type``.
        """
        self.types.append(HierarkeyType(type=type, serialize=serialize, unserialize=unserialize))

    def set_global(self, cache_namespace: str = None) -> type:
        """
        Decorator. Attaches the global key-value store of this hierarchy to an object.

        :param cache_namespace: Optional. A custom namespace used for caching. By default this is
                                constructed from the name of the class this is applied to and
                                the ``attribute_name`` of this ``Hierarkey`` object.
        """

        if isinstance(cache_namespace, type):
            raise ImproperlyConfigured('Incorrect decorator usage, you need to use .add_global() '
                                       'instead of .add_global')

        def wrapper(wrapped_class):
            if issubclass(wrapped_class, models.Model):
                raise ImproperlyConfigured('Hierarkey.add_global() can only be invoked on a normal class, '
                                           'not on a Django model.')
            if not issubclass(wrapped_class, GlobalSettingsBase):
                raise ImproperlyConfigured('You should use .add_global() on a class that inherits from '
                                           'GlobalSettingsBase.')

            _cache_namespace = cache_namespace or ('%s_%s' % (wrapped_class.__name__, self.attribute_name))

            model_name = '%s_%sStore' % (wrapped_class.__name__, self.attribute_name.title())
            if getattr(sys.modules[wrapped_class.__module__], model_name, None):
                # Already wrapped
                return wrapped_class

            attrs = self._create_attrs(wrapped_class, (("key",),))
            kv_model = self._create_model(model_name, attrs)

            def init(self, *args, object=None, **kwargs):
                super(kv_model, self).__init__(*args, **kwargs)

            setattr(kv_model, '__init__', init)

            hierarkey = self

            def prop(iself):
                from .proxy import HierarkeyProxy

                attrname = '_hierarkey_proxy_{}_{}'.format(_cache_namespace, self.attribute_name)
                cached = getattr(iself, attrname, None)
                if not cached:
                    cached = HierarkeyProxy._new(iself, type=kv_model, hierarkey=hierarkey,
                                                 cache_namespace=_cache_namespace)
                    setattr(iself, attrname, cached)
                return cached

            setattr(sys.modules[wrapped_class.__module__], model_name, kv_model)
            setattr(wrapped_class, '_%s_objects' % self.attribute_name, kv_model.objects)
            setattr(wrapped_class, self.attribute_name, property(prop))
            self.global_class = wrapped_class
            return wrapped_class

        return wrapper

    def add(self, cache_namespace: str = None, parent_field: str = None) -> type:
        """
        Decorator. Attaches a global key-value store to a Django model.

        :param cache_namespace: Optional. A custom namespace used for caching. By default this is
                                constructed from the name of the class this is applied to and
                                the ``attribute_name`` of this ``Hierarkey`` object.
        :param parent_field: Optional. The name of a field of this model that refers to the parent
                             in the hierarchy. This must be a ``ForeignKey`` field.
        """
        if isinstance(cache_namespace, type):
            raise ImproperlyConfigured('Incorrect decorator usage, you need to use .add() instead of .add')

        def wrapper(model):
            if not issubclass(model, models.Model):
                raise ImproperlyConfigured('Hierarkey.add() can only be invoked on a Django model')

            _cache_namespace = cache_namespace or ('%s_%s' % (model.__name__, self.attribute_name))

            attrs = self._create_attrs(model, (("object", "key"),))
            attrs['object'] = models.ForeignKey(model, related_name='_%s_objects' % self.attribute_name,
                                                on_delete=models.CASCADE)
            model_name = '%s_%sStore' % (model.__name__, self.attribute_name.title())
            kv_model = self._create_model(model_name, attrs)

            setattr(sys.modules[model.__module__], model_name, kv_model)

            hierarkey = self

            def prop(iself):
                from .proxy import HierarkeyProxy

                attrname = '_hierarkey_proxy_{}_{}'.format(_cache_namespace, self.attribute_name)
                cached = getattr(iself, attrname, None)
                if not cached:
                    try:
                        parent = getattr(iself, parent_field) if parent_field else None
                    except models.ObjectDoesNotExist:  # pragma: no cover
                        parent = None

                    if not parent and hierarkey.global_class:
                        parent = hierarkey.global_class()

                    cached = HierarkeyProxy._new(
                        iself,
                        type=kv_model,
                        hierarkey=hierarkey,
                        parent=parent,
                        cache_namespace=_cache_namespace
                    )
                    setattr(iself, attrname, cached)
                return cached

            setattr(model, self.attribute_name, property(prop))

            return model

        return wrapper


class GlobalSettingsBase:
    """
    Base class for objects with a global settings storage attached. This class does not
    add any functionality, it only makes global settings behave more consistent to
    object-level settings.
    """

    pk = '_global'
