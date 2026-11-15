"""Shared helpers for the built-in system pages (terms, privacy, support).

Both ``SystemPageView`` and the footer context processor decide whether a system
page is reachable, so the logic lives here to keep the two in agreement.
"""

import html
import re

# System pages whose footer link serves content from a local route.
SYSTEM_CONTENT_SLUGS = ('terms', 'privacy', 'support')

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_INVISIBLE_CHARS = (' ', '​', '‌', '‍', '﻿')


def has_i18n_content(value):
    """True when a stored i18n value has visible text in at least one locale.

    Empty rich-text markup (``<p></p>``), character references (``&nbsp;``,
    ``&#160;``) and invisible characters do not count as content.
    """
    data = getattr(value, 'data', value)
    values = data.values() if isinstance(data, dict) else (data,)
    for item in values:
        if item is None:
            continue
        text = html.unescape(_HTML_TAG_RE.sub('', str(item)))
        for char in _INVISIBLE_CHARS:
            text = text.replace(char, '')
        if text.strip():
            return True
    return False
