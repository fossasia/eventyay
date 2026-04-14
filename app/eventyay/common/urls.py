from contextlib import suppress
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

from django.conf import settings
from django.urls import register_converter, resolve, reverse
from urlman import Urls


# Custom path converter for organizer slugs that allows dots
class OrganizerSlugConverter:
    regex = r'[a-zA-Z0-9_.-]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(OrganizerSlugConverter, 'orgslug')


def get_base_url(event=None, url=None):
    if url and url.startswith('/orga'):
        return settings.SITE_URL
    if event:
        if event.display_settings['html_export_url'] and url:
            with suppress(Exception):
                resolved = resolve(url)
                if 'agenda' in resolved.namespaces:
                    return event.display_settings['html_export_url']
        if event.custom_domain:
            return event.custom_domain
    return settings.SITE_URL


def build_absolute_uri(urlname, event=None, args=None, kwargs=None):
    url = get_base_url(event)
    return urljoin(url, reverse(urlname, args=args, kwargs=kwargs))


def get_url_scheme(value: str | None) -> str:
    if not isinstance(value, str):
        return ''
    return urlsplit(value).scheme.lower()


def is_http_url(value: str | None) -> bool:
    return get_url_scheme(value) in ('http', 'https')


def is_file_url(value: str | None) -> bool:
    return get_url_scheme(value) == 'file'


def normalize_url_scheme(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme:
        return value
    return urlunsplit(parsed._replace(scheme=parsed.scheme.lower()))


def get_url_origin(value: str | None) -> str | None:
    if not is_http_url(value):
        return None

    parsed = urlsplit(value)
    if not parsed.netloc:
        return None

    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), '', '', ''))


def get_file_url_path(value: str | None) -> str | None:
    if not is_file_url(value):
        return None

    parsed = urlsplit(value)
    return f'{parsed.netloc}{parsed.path}' or None


class EventUrls(Urls):
    def get_hostname(self, url):
        url = get_base_url(self.instance.event, url)
        return urlparse(url).netloc

    def get_scheme(self, url):
        url = get_base_url(self.instance.event, url)
        return urlparse(url).scheme
