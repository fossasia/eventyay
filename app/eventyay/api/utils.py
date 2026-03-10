from typing import Optional

from urllib.parse import urlparse


def get_protocol(url: Optional[str]) -> str:
    """Return the URL scheme (protocol) for *url*, lower-cased.

    If *url* is ``None``, empty, whitespace-only, or has no explicit
    scheme (e.g. a schemeless URL like ``//example.com/path`` or a
    bare hostname like ``example.com``), the function returns
    ``'https'`` as a safe default so callers never receive an empty
    string that would produce a malformed domain such as
    ``://example.com``.

    Args:
        url: The URL string to inspect. ``None`` is accepted and treated
            as empty.

    Returns:
        The scheme component of *url* in lower-case, or ``'https'`` when
        no scheme can be determined.
    """
    # Normalize/strip whitespace so that raw user input like '   '
    # is treated as empty rather than passed directly to urlparse.
    if not url or not url.strip():
        return 'https'
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    return scheme if scheme else 'https'
