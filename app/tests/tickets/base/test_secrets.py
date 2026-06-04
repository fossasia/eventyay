import base64
import struct
import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Organizer
from eventyay.base.secrets import (
    RandomTicketSecretGenerator,
    Sig1TicketSecretGenerator,
)

schemes = (
    (RandomTicketSecretGenerator, False),
    (Sig1TicketSecretGenerator, True),
)


@pytest.fixture(scope='function')
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='pretix.plugins.banktransfer',
    )
    with scope(organizer=o):
        yield event


@pytest.mark.django_db
@pytest.mark.parametrize('scheme', schemes)
def test_force_invalidate(event, scheme):
    item = event.items.create(name='Foo', default_price=0)
    generator, input_dependent = scheme
    g = generator(event)

    first = g.generate_secret(item, None, None, current_secret=None, force_invalidate=False)
    assert first
    second = g.generate_secret(item, None, None, current_secret=first, force_invalidate=True)
    assert first != second


@pytest.mark.django_db
@pytest.mark.parametrize('scheme', schemes)
def test_keep_same(event, scheme):
    item = event.items.create(name='Foo', default_price=0)
    generator, input_dependent = scheme
    g = generator(event)

    first = g.generate_secret(item, None, None, current_secret=None, force_invalidate=False)
    assert first
    second = g.generate_secret(item, None, None, current_secret=first, force_invalidate=False)
    assert first == second


@pytest.mark.django_db
@pytest.mark.parametrize('scheme', schemes)
def test_change_if_required(event, scheme):
    item = event.items.create(name='Foo', default_price=0)
    item2 = event.items.create(name='Bar', default_price=0)
    generator, input_dependent = scheme
    g = generator(event)

    first = g.generate_secret(item, None, None, current_secret=None, force_invalidate=False)
    assert first
    second = g.generate_secret(item2, None, None, current_secret=first, force_invalidate=False)
    if input_dependent:
        assert first != second
    else:
        assert first == second


@pytest.mark.django_db
@pytest.mark.parametrize('scheme', schemes)
def test_change_if_invalid(event, scheme):
    item = event.items.create(name='Foo', default_price=0)
    generator, input_dependent = scheme
    g = generator(event)

    first = 'blafasel'
    second = g.generate_secret(item, None, None, current_secret=first, force_invalidate=False)
    if input_dependent:
        assert first != second


@pytest.mark.django_db
def test_sig1_parse_invalid_secret_returns_none(event):
    with scope(organizer=event.organizer):
        generator = Sig1TicketSecretGenerator(event)
        generator._generate_keys()

        # Empty string
        assert generator._parse('') is None

        # Invalid base64 padding (binascii.Error)
        assert generator._parse('abc') is None

        # Version not equal to 1 (ValueError)
        invalid_version = base64.b64encode(b'\x02\x00\x00\x00\x00').decode()[::-1]
        assert generator._parse(invalid_version) is None

        # Too short payload (len < 5)
        assert generator._parse(base64.b64encode(b'\x01\x00').decode()[::-1]) is None

        # Invalid signature verification (InvalidSignature) - craft a payload with a wrong signature value
        dummy_payload = b'test'
        dummy_signature = b'0' * 64
        invalid_sig_bytes = bytes([0x01]) + struct.pack('>H', len(dummy_payload)) + struct.pack('>H', len(dummy_signature)) + dummy_payload + dummy_signature
        invalid_sig_secret = base64.b64encode(invalid_sig_bytes).decode()[::-1]
        assert generator._parse(invalid_sig_secret) is None

        # Valid signature framing but invalid protobuf payload (DecodeError)
        invalid_proto_secret = base64.b64encode(generator._sign_payload(b'\xff')).decode()[::-1]
        assert generator._parse(invalid_proto_secret) is None

