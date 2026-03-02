from urllib.parse import urlparse


def get_protocol(url: str) -> str:
    """Return the URL scheme (protocol) for *url*, lower-cased.

    If *url* is ``None``, empty, or has no explicit scheme (e.g. a
    schemeless URL like ``//example.com/path``), the function returns
    ``'https'`` as a safe default so callers never receive an empty
    string that would produce a malformed domain such as
    ``://example.com``.

    Args:
        url: The URL string to inspect.

    Returns:
        The scheme component of *url* in lower-case, or ``'https'`` when
        no scheme can be determined.
    """
    if not url:
        return 'https'
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    return scheme if scheme else 'https'
