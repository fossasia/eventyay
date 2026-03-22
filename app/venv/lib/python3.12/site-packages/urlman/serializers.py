try:
    from rest_framework.serializers import Field
except ImportError:  # pragma: no cover

    class Field:
        def __init__(self, **kwargs):
            pass


class UrlManField(Field):
    """Serializer class for Django Restframework."""

    def __init__(self, urls, attribute="urls", full=True, **kwargs):
        kwargs.setdefault("read_only", True)
        kwargs.setdefault("write_only", False)
        kwargs.setdefault("label", None)
        kwargs.setdefault("source", "*")
        super().__init__(**kwargs)
        self.urls = urls
        self.url_attribute = attribute
        self.full = full

    def to_representation(self, value):
        url_class = getattr(value, self.url_attribute)
        return {
            url: (
                getattr(url_class, url).full() if self.full else getattr(url_class, url)
            )
            for url in self.urls
        }
