import pytest

from eventyay.helpers.u2f import websafe_decode, websafe_encode


@pytest.mark.parametrize(
    'raw',
    [
        b'\x01\x02\x03credential',
        b'',
        b'\xff' * 32,  # padding would be stripped
        b'\xfb\xef?',  # exercises the URL-safe '-' and '_' alphabet
    ],
)
def test_websafe_encode_round_trips_bytes(raw):
    """Bytes are the normal input: WebAuthn credential ids and public keys are bytes."""
    encoded = websafe_encode(raw)
    assert isinstance(encoded, str)
    assert '=' not in encoded
    assert websafe_decode(encoded) == raw


def test_websafe_encode_accepts_str():
    encoded = websafe_encode('hello')
    assert encoded == 'aGVsbG8'
    assert websafe_decode(encoded) == b'hello'
