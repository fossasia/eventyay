import gzip
import socket
import threading
import time

import pytest

from eventyay.base.services import mail as mail_service


@pytest.fixture
def serve(monkeypatch):
    """Start a one-shot local HTTP server driven by `handler(conn)`; returns its image URL."""
    monkeypatch.setenv('NO_PROXY', '127.0.0.1')
    monkeypatch.setenv('no_proxy', '127.0.0.1')
    servers = []

    def start(handler):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        servers.append(server)

        def run():
            try:
                conn, _ = server.accept()
                conn.recv(65536)
                handler(conn)
                conn.close()
            except OSError:
                pass

        threading.Thread(target=run, daemon=True).start()
        return f'http://127.0.0.1:{server.getsockname()[1]}/logo.png'

    yield start
    for server in servers:
        server.close()


def _response(status, body, extra=''):
    head = f'HTTP/1.1 {status}\r\nContent-Length: {len(body)}\r\n{extra}\r\n'.encode()
    return head + body


def test_valid_image_is_returned(serve):
    url = serve(lambda conn: conn.sendall(_response('200 OK', b'\x89PNG-bytes')))
    assert mail_service.convert_image_to_cid(url, 'cid1') is not None


def test_gzip_encoded_image_is_decoded(serve):
    body = gzip.compress(b'a' * 5000)
    url = serve(lambda conn: conn.sendall(_response('200 OK', body, 'Content-Encoding: gzip\r\n')))
    image = mail_service.convert_image_to_cid(url, 'cid1')
    assert image is not None
    assert len(image.get_payload(decode=True)) == 5000


def test_404_page_is_not_attached_as_image(serve):
    url = serve(lambda conn: conn.sendall(_response('404 Not Found', b'<html>nope</html>')))
    assert mail_service.convert_image_to_cid(url, 'cid1') is None


def test_oversized_image_is_rejected(serve, monkeypatch):
    monkeypatch.setattr(mail_service, 'CID_IMAGE_MAX_BYTES', 1024)
    url = serve(lambda conn: conn.sendall(_response('200 OK', b'x' * 4096)))
    assert mail_service.convert_image_to_cid(url, 'cid1') is None


def test_dribbling_server_is_cut_off_at_the_deadline(serve, monkeypatch):
    """A server sending one byte at a time must not hold the worker past the deadline."""
    monkeypatch.setattr(mail_service, 'CID_IMAGE_DEADLINE_SECONDS', 1)

    def dribble(conn):
        conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\n')
        for _ in range(200):
            conn.sendall(b'x')
            time.sleep(0.3)

    url = serve(dribble)
    start = time.monotonic()
    assert mail_service.convert_image_to_cid(url, 'cid1') is None
    assert time.monotonic() - start < 5


def test_connection_dropped_mid_body_is_handled(serve):
    url = serve(lambda conn: conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 100000\r\n\r\npartial'))
    assert mail_service.convert_image_to_cid(url, 'cid1') is None
