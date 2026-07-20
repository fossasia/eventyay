"""
Server-side HTML sanitization for Tiptap editor output.

Uses nh3 (Rust/Ammonia-based) which is already a project dependency.
Two sanitizer profiles are provided:

- ``sanitize_rich_text`` – for general rich text fields (adds safe link rel attributes).
- ``sanitize_email_html`` – for email body fields (omits rel injection so email
  clients do not display unwanted attributes).
"""

from collections.abc import Callable, Mapping

import nh3

_RICH_TEXT_TAGS: frozenset[str] = frozenset({
    'p', 'br', 'strong', 'b', 'em', 'i', 'u',
    'ul', 'ol', 'li', 'a', 'blockquote',
})

_EMAIL_TAGS: frozenset[str] = _RICH_TEXT_TAGS | frozenset({'span', 'img'})

_LINK_ATTRIBUTES: dict[str, set[str]] = {'a': {'href'}}

_EMAIL_ATTRIBUTES: dict[str, set[str]] = {
    # ``class`` on anchors supports template buttons such as Download PDF / Join online.
    'a': {'href', 'class'},
    'span': {'data-variable', 'class'},
    # QR placeholders render as data-URI images; CID conversion runs after sanitize.
    'img': {'src', 'alt', 'width', 'height'},
}

# Align with bleach ALLOWED_PROTOCOLS in base.templatetags.rich_text.
_SAFE_URL_SCHEMES: frozenset[str] = frozenset({'http', 'https', 'mailto', 'tel'})
# Email bodies may embed QR codes as ``data:image/png;base64,…`` before CID inlining.
_EMAIL_URL_SCHEMES: frozenset[str] = _SAFE_URL_SCHEMES | frozenset({'data'})


def _attribute_filter(allowed: Mapping[str, set[str]]) -> Callable[[str, str, str], str | None]:
    """Strict attribute allowlist.

    nh3 still keeps some global attributes (e.g. ``title``) when they are
    omitted from ``attributes=``; this filter removes them.
    """

    def filter_attr(tag: str, attr: str, value: str) -> str | None:
        if attr in allowed.get(tag, ()):
            return value
        return None

    return filter_attr


# ``rel`` is included so nh3 ``link_rel`` injection is not stripped by the filter.
_RICH_TEXT_ATTR_FILTER = _attribute_filter({'a': {'href', 'rel'}})
_EMAIL_ATTR_FILTER = _attribute_filter(_EMAIL_ATTRIBUTES)


def _clean(
    html: str,
    *,
    tags: frozenset[str],
    attributes: Mapping[str, set[str]],
    attribute_filter: Callable[[str, str, str], str | None],
    link_rel: str | None,
    url_schemes: frozenset[str] = _SAFE_URL_SCHEMES,
) -> str:
    if not html:
        return html
    return nh3.clean(
        html,
        tags=tags,
        attributes=attributes,
        attribute_filter=attribute_filter,
        url_schemes=url_schemes,
        link_rel=link_rel,
    )


def sanitize_rich_text(html: str) -> str:
    """Sanitize HTML from the simple rich text editor profile."""
    return _clean(
        html,
        tags=_RICH_TEXT_TAGS,
        attributes=_LINK_ATTRIBUTES,
        attribute_filter=_RICH_TEXT_ATTR_FILTER,
        link_rel='noopener noreferrer',
    )


def sanitize_email_html(html: str) -> str:
    """Sanitize HTML from the email body editor profile.

    Like ``sanitize_rich_text``, but does not inject ``rel`` (email clients are
    picky), allows ``span`` for placeholder chips, ``img`` for QR placeholders,
    and ``data:`` image sources.
    """
    return _clean(
        html,
        tags=_EMAIL_TAGS,
        attributes=_EMAIL_ATTRIBUTES,
        attribute_filter=_EMAIL_ATTR_FILTER,
        link_rel=None,
        url_schemes=_EMAIL_URL_SCHEMES,
    )
