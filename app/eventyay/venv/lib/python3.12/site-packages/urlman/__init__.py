import string

try:
    from urlparse import urlunparse
except ImportError:  # pragma: no cover
    from urllib.parse import urlunparse


__version__ = "2.0.3"


class UrlsMetaclass(type):
    """
    Metaclass which makes attribute access instantiate the class with
    the instance.
    """

    callables = ["urls", "get_url", "get_example_url", "get_scheme", "get_hostname"]

    def __new__(self, name, bases, attrs):
        # Collect patterns off of the attrs
        attrs["urls"] = {}
        for name, item in list(attrs.items()):
            if name not in self.callables and not name.startswith("__"):
                attrs["urls"][name] = item
                del attrs[name]
        # Initialise
        return type.__new__(self, name, bases, attrs)

    def __get__(self, instance, klass):
        return self(klass, instance, self.__name__)


class Urls(metaclass=UrlsMetaclass):
    """
    Special object which lets you specify URL strings for objects.

    Declare urls as string attributes on the object in _python 3_ string
    format. If you need to you can also specify a handler function for a url.
    """

    def __init__(self, klass, instance, name):
        self.klass = klass
        self.instance = instance
        self.context = {"self": self.instance}
        self.context.update(self.urls)
        self.__qualname__ = ".".join((klass.__qualname__, name))
        self.__objclass__ = klass
        self.__name__ = name
        self.__wrapped__ = None

    def __getattr__(self, attr):
        return self.get_url(attr)

    def get_url(self, attr: str) -> "UrlString":
        # Get the URL value
        try:
            url = self.urls[attr]
        except KeyError:
            raise ValueError(
                "No URL called %r on %r" % (attr, self.instance.__class__.__name__)
            )
        else:
            if callable(url):
                url = url(self.instance)
            value = UrlFormatter(self).vformat(url, [], {})
        url = UrlString(value)
        url.parent = self
        return url

    def get_example_url(self, attr):
        # Get the URL value
        try:
            url = self.urls[attr]
        except KeyError:
            raise ValueError("No URL called %r" % attr)
        else:
            if callable(url):
                url = url(self.instance)
            value = UrlFormatter(self, example=True).vformat(url, [], {})
        return value

    def get_scheme(self, url: "UrlString"):
        return "http"

    def get_hostname(self, url: "UrlString"):
        return "localhost"


class UrlString(str):
    """
    Special string subclass for URLs (for future with/without host modes)
    """

    def full(self, scheme="", hostname="", port="", params="", query="", fragment=""):

        if hasattr(self, "parent") and self.parent is not None:
            scheme = scheme or self.parent.get_scheme(self)
            hostname = hostname or self.parent.get_hostname(self)

        netloc = hostname
        if port:
            netloc = "%s:%s" % (netloc, port)
        return urlunparse((scheme, netloc, self, params, query, fragment))


class UrlFormatter(string.Formatter):
    """
    Special string formatter that calls methods.
    """

    def __init__(self, urls, example=False):
        self.example = example
        self.urls = urls

    def get_value(self, key, args, kwargs):
        # First, try looking up the key in our own URLs
        try:
            if self.example:
                value = self.urls.get_example_url(key)
            else:
                value = self.urls.get_url(key)
        except ValueError:
            pass
        else:
            return value
        # Now, fall back to looking in the context (just self)
        if key == "self":
            if self.example:
                return PrintMe("self")
            else:
                return self.urls.instance
        # Uh oh.
        raise KeyError("No other URL called %r for use in URL format" % key)

    def format_field(self, value, format_spec):
        if callable(value):
            value = value()
        return string.Formatter.format_field(self, value, format_spec)


class PrintMe(object):
    """Object which prints itself, essentially."""

    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, attr):
        return PrintMe(self.obj + "." + attr)

    def __str__(self):
        return "{%s}" % self.obj
