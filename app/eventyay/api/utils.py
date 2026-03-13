from urllib.parse import urlparse


def get_protocol(url: str) -> str:
    parsed = urlparse(url)
    protocol = parsed.scheme
    if not protocol:
        return 'https'
    return protocol.lower()
