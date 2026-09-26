import gzip

from django.http import HttpResponse
from django.middleware.gzip import GZipMiddleware
from django.utils.cache import patch_vary_headers

GZIP_MIN_BYTES = 860
SKIPPED_RESPONSE_HEADERS = {'content-length', 'content-encoding'}
COMPRESSIBLE_CONTENT_TYPES = {
    'application/javascript',
    'application/json',
    'application/manifest+json',
    'application/xml',
    'image/svg+xml',
}


def accepts_gzip(accept_encoding: str) -> bool:
    """Return whether gzip is acceptable. A q-value of 0 rejects it."""
    gzip_quality = None
    wildcard_quality = None
    for item in accept_encoding.split(','):
        parts = [part.strip() for part in item.split(';') if part.strip()]
        if not parts:
            continue
        coding = parts[0].lower()
        quality = 1.0
        for param in parts[1:]:
            name, separator, value = param.partition('=')
            if separator and name.strip().lower() == 'q':
                try:
                    quality = float(value.strip())
                except ValueError:
                    quality = 0.0
        if coding == 'gzip':
            gzip_quality = quality
        elif coding == '*':
            wildcard_quality = quality
    if gzip_quality is not None:
        return gzip_quality > 0
    if wildcard_quality is not None:
        return wildcard_quality > 0
    return False


def compressible_content_type(content_type: str) -> bool:
    media_type = content_type.split(';', 1)[0].strip().lower()
    return media_type.startswith('text/') or media_type in COMPRESSIBLE_CONTENT_TYPES


def copy_response_headers(source, target):
    for header, value in source.items():
        if header.lower() in SKIPPED_RESPONSE_HEADERS:
            continue
        target[header] = value
    target._csp_ignore = getattr(source, '_csp_ignore', False)


def with_accept_encoding_vary(response):
    vary = response.get('Vary')
    if not vary:
        response['Vary'] = 'Accept-Encoding'
        return
    parts = [part.strip() for part in vary.split(',') if part.strip()]
    if not any(part.lower() == 'accept-encoding' for part in parts):
        parts.append('Accept-Encoding')
        response['Vary'] = ', '.join(parts)


def replacement_response(response, body, *, encoding=None):
    replacement = HttpResponse(
        body,
        content_type=response.get('Content-Type'),
        status=response.status_code,
    )
    copy_response_headers(response, replacement)
    if encoding:
        replacement['Content-Encoding'] = encoding
        with_accept_encoding_vary(replacement)
    return replacement


def gzip_if_accepted(request, response):
    """Compress text responses when the browser asked for gzip.

    Local runserver and the video fallback path do not sit behind a
    compressing proxy, so large JS and CSS would otherwise be sent raw.
    """
    if getattr(response, 'status_code', None) != 200 or response.get('Content-Encoding'):
        return response
    if not accepts_gzip(request.META.get('HTTP_ACCEPT_ENCODING', '')):
        return response
    if not compressible_content_type(response.get('Content-Type', '')):
        return response
    streaming = getattr(response, 'streaming', False)
    if streaming:
        body = b''.join(response.streaming_content)
    else:
        body = response.content
    if len(body) < GZIP_MIN_BYTES:
        if streaming:
            return replacement_response(response, body)
        return response
    compressed = gzip.compress(body, compresslevel=5)
    if len(compressed) >= len(body):
        if streaming:
            return replacement_response(response, body)
        return response
    return replacement_response(response, compressed, encoding='gzip')


class CompressibleGZipMiddleware(GZipMiddleware):
    """Gzip text responses and leave rejected or binary bodies unchanged.

    Django treats any Accept-Encoding that mentions gzip as acceptance,
    including gzip;q=0, and it compresses streaming files without looking
    at the content type.
    """

    def process_response(self, request, response):
        if response.has_header('Content-Encoding'):
            return response
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if not accepts_gzip(accept_encoding):
            if 'gzip' in accept_encoding.lower():
                patch_vary_headers(response, ('Accept-Encoding',))
            return response
        content_type = response.get('Content-Type', '')
        if content_type and not compressible_content_type(content_type):
            return response
        return super().process_response(request, response)
