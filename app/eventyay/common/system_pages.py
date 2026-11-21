"""Shared helpers for the built-in system pages (terms, privacy, support).

Both ``SystemPageView`` and the footer context processor decide whether a system
page is reachable, so the logic lives here to keep the two in agreement.
"""

import html
import re

from i18nfield.strings import LazyI18nString

# System pages whose footer link serves content from a local route.
SYSTEM_CONTENT_SLUGS = ('terms', 'privacy', 'support')

_HTML_TAG_RE = re.compile(r'<[^>]+>')
# Standalone media is content even without surrounding text.
_MEDIA_TAG_RE = re.compile(r'<(img|iframe|video|audio|svg|embed|object)[\s>/]', re.IGNORECASE)
_INVISIBLE_CHARS = tuple(chr(code) for code in (0x00A0, 0x200B, 0x200C, 0x200D, 0xFEFF))


def has_i18n_content(value):
    """True when a stored i18n value has renderable content in at least one locale.

    Empty rich-text markup (``<p></p>``), character references (``&nbsp;``,
    ``&#160;``) and invisible characters do not count; standalone media does.
    """
    data = getattr(value, 'data', value)
    values = data.values() if isinstance(data, dict) else (data,)
    for item in values:
        if item is None:
            continue
        raw = str(item)
        if _MEDIA_TAG_RE.search(raw):
            return True
        text = html.unescape(_HTML_TAG_RE.sub('', raw))
        for char in _INVISIBLE_CHARS:
            text = text.replace(char, '')
        if text.strip():
            return True
    return False


def available_system_page_slugs(candidate_slugs, settings):
    """Of ``candidate_slugs``, return those that would render instead of 404.

    A page is available when its settings text has content, or a database ``Page``
    with the same slug has content. At most one database query is run, only for
    the candidates that lack settings text.
    """
    from eventyay.base.models.page import Page

    available = set()
    without_settings_text = []
    for slug in candidate_slugs:
        if has_i18n_content(settings.get(f'footer_page_{slug}_text', as_type=LazyI18nString)):
            available.add(slug)
        else:
            without_settings_text.append(slug)
    if without_settings_text:
        db_pages = {}
        for page in Page.objects.filter(slug__in=without_settings_text).order_by('pk'):
            db_pages.setdefault(page.slug, page)
        for slug, page in db_pages.items():
            if has_i18n_content(page.text):
                available.add(slug)
    return available
