"""
Server-side HTML sanitization for Tiptap editor output.

Uses nh3 (Rust/Ammonia-based) which is already a project dependency.
Two sanitizer profiles are provided:

- ``sanitize_rich_text`` – for general rich text fields (adds safe link rel attributes).
- ``sanitize_email_html`` – for email body fields (omits rel injection so email
  clients do not display unwanted attributes).
"""

import nh3

_RICH_TEXT_TAGS: frozenset[str] = frozenset({
    'p', 'br', 'strong', 'b', 'em', 'i', 'u',
    'ul', 'ol', 'li', 'a', 'blockquote',
})

_EMAIL_TAGS: frozenset[str] = _RICH_TEXT_TAGS | frozenset({'span'})

_LINK_ATTRIBUTES: dict[str, set[str]] = {'a': {'href', 'title'}}

_SAFE_URL_SCHEMES: frozenset[str] = frozenset({'http', 'https'})


def sanitize_rich_text(html: str) -> str:
    """Sanitize HTML from the simple rich text editor profile.

    Strips all tags and attributes not in the allowed set, rejects any
    link ``href`` that is not an ``http://`` or ``https://`` URL, and
    adds ``rel="noopener noreferrer"`` to all anchor elements.
    """
    if not html:
        return html
    return nh3.clean(
        html,
        tags=_RICH_TEXT_TAGS,
        attributes=_LINK_ATTRIBUTES,
        url_schemes=_SAFE_URL_SCHEMES,
        link_rel='noopener noreferrer',
    )


def sanitize_email_html(html: str) -> str:
    """Sanitize HTML from the email body editor profile.

    Identical to ``sanitize_rich_text`` except that ``rel`` attributes are
    not injected, since many email clients display them as visible text or
    strip the anchor entirely when unexpected attributes are present.
    ``span`` is additionally allowed for placeholder chip rendering.
    """
    if not html:
        return html
    return nh3.clean(
        html,
        tags=_EMAIL_TAGS,
        attributes=_LINK_ATTRIBUTES,
        url_schemes=_SAFE_URL_SCHEMES,
        link_rel=None,
    )
