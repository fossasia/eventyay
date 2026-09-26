import gzip

from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory

from eventyay.common.gzip import GZIP_MIN_BYTES, gzip_if_accepted

LAST_MODIFIED = 'Wed, 21 Oct 2015 07:28:00 GMT'


def test_small_streaming_replacement_keeps_validators():
    request = RequestFactory().get('/', HTTP_ACCEPT_ENCODING='gzip')
    original = StreamingHttpResponse(iter([b'console.log(1)\n']), content_type='application/javascript')
    original['Last-Modified'] = LAST_MODIFIED
    original['Cache-Control'] = 'public, max-age=300'
    original['ETag'] = '"asset"'

    result = gzip_if_accepted(request, original)

    assert result.status_code == 200
    assert result.content == b'console.log(1)\n'
    assert result['Last-Modified'] == LAST_MODIFIED
    assert result['Cache-Control'] == 'public, max-age=300'
    assert result['ETag'] == '"asset"'
    assert 'Content-Encoding' not in result


def test_compressed_replacement_keeps_validators():
    request = RequestFactory().get('/', HTTP_ACCEPT_ENCODING='gzip')
    body = b'console.log("hello");\n' * 80
    assert len(body) >= GZIP_MIN_BYTES
    original = HttpResponse(body, content_type='application/javascript')
    original['Last-Modified'] = LAST_MODIFIED
    original['Cache-Control'] = 'public, max-age=300'
    original['Vary'] = 'Cookie'

    result = gzip_if_accepted(request, original)

    assert gzip.decompress(result.content) == body
    assert result['Content-Encoding'] == 'gzip'
    assert result['Last-Modified'] == LAST_MODIFIED
    assert result['Cache-Control'] == 'public, max-age=300'
    assert 'Cookie' in result['Vary']
    assert 'Accept-Encoding' in result['Vary']
