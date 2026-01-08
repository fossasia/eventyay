import django.utils.translation
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.defaultfilters import date
from jinja2 import Environment

from eventyay.helpers.templatetags.thumb import thumb

from .helpers.jinja import url_for


def static_url(path: str = '') -> str:
    """Return a resolved static URL using Django's staticfiles storage.

    Uses staticfiles_storage.url() to generate URLs, which handles
    versioning, custom backends, and proper path resolution.
    """
    return staticfiles_storage.url(path)


jj_globals = {
    'url_for': url_for,
    'settings': settings,
    'site_url': settings.SITE_URL,
    'static_url': static_url,
}

jj_filters = {
    'thumb': thumb,
    'format_date': date,
}


def environment(**options) -> Environment:
    env = Environment(**options)
    # This method is from `jinja2.ext.i18n`
    env.install_gettext_translations(django.utils.translation, newstyle=True)
    env.globals.update(jj_globals)
    env.filters.update(jj_filters)
    return env
