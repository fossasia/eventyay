import gzip

from django.http import HttpResponse

GZIP_MIN_BYTES = 860
SKIPPED_RESPONSE_HEADERS = {'content-length', 'content-encoding'}


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
    if 'gzip' not in request.META.get('HTTP_ACCEPT_ENCODING', ''):
        return response
    content_type = response.get('Content-Type', '').split(';', 1)[0].strip().lower()
    compressible = (
        content_type.startswith('text/')
        or content_type in {
            'application/javascript',
            'application/json',
            'application/manifest+json',
            'application/xml',
            'image/svg+xml',
        }
    )
    if not compressible:
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
