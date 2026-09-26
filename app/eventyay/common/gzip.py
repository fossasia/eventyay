import gzip

from django.http import HttpResponse

GZIP_MIN_BYTES = 860


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
    if getattr(response, 'streaming', False):
        body = b''.join(response.streaming_content)
    else:
        body = response.content
    cache_control = response.get('Cache-Control')
    csp_ignore = getattr(response, '_csp_ignore', False)
    if len(body) < GZIP_MIN_BYTES:
        # The file stream is already consumed, so send the bytes we read.
        plain = HttpResponse(body, content_type=response.get('Content-Type'), status=response.status_code)
        if cache_control:
            plain['Cache-Control'] = cache_control
        plain._csp_ignore = csp_ignore
        return plain
    compressed = gzip.compress(body, compresslevel=5)
    if len(compressed) >= len(body):
        plain = HttpResponse(body, content_type=response.get('Content-Type'), status=response.status_code)
        if cache_control:
            plain['Cache-Control'] = cache_control
        plain._csp_ignore = csp_ignore
        return plain
    compressed_response = HttpResponse(
        compressed,
        content_type=response.get('Content-Type'),
        status=response.status_code,
    )
    compressed_response['Content-Encoding'] = 'gzip'
    compressed_response['Vary'] = 'Accept-Encoding'
    if cache_control:
        compressed_response['Cache-Control'] = cache_control
    compressed_response._csp_ignore = csp_ignore
    return compressed_response
