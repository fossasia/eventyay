# Copyright (c) 2018 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


"""
Minimal CBOR implementation supporting a subset of functionality and types
required for FIDO 2 CTAP.

Use the :func:`encode`, :func:`decode` and :func:`decode_from` functions to encode
and decode objects to/from CBOR.
"""

from __future__ import annotations

import struct
from types import UnionType
from typing import Any, Callable, Mapping, Sequence, TypeAlias

CborType: TypeAlias = int | bool | str | bytes | Sequence[Any] | Mapping[Any, Any]

# TODO: Requires Python 3.12, replace with collections.abc.Buffer
Buffer: TypeAlias = bytes | bytearray | memoryview


def _dump_int(data: int, mt: int = 0) -> bytes:
    if data < 0:
        mt = 1
        data = -1 - data

    mt = mt << 5
    fmt: str
    args: tuple[int, ...]
    if data <= 23:
        fmt, args = ">B", (mt | data,)
    elif data <= 0xFF:
        fmt, args = ">BB", (mt | 24, data)
    elif data <= 0xFFFF:
        fmt, args = ">BH", (mt | 25, data)
    elif data <= 0xFFFFFFFF:
        fmt, args = ">BI", (mt | 26, data)
    else:
        fmt, args = ">BQ", (mt | 27, data)
    return struct.pack(fmt, *args)


def _dump_bool(data: bool) -> bytes:
    return b"\xf5" if data else b"\xf4"


def _dump_list(data: Sequence[CborType]) -> bytes:
    return _dump_int(len(data), mt=4) + b"".join([encode(x) for x in data])


def _sort_keys(entry):
    key = entry[0]
    return key[0], len(key), key


def _dump_dict(data: Mapping[CborType, CborType]) -> bytes:
    items = [(encode(k), encode(v)) for k, v in data.items()]
    items.sort(key=_sort_keys)
    return _dump_int(len(items), mt=5) + b"".join([k + v for (k, v) in items])


def _dump_bytes(data: bytes) -> bytes:
    return _dump_int(len(data), mt=2) + data


def _dump_text(data: str) -> bytes:
    data_bytes = data.encode("utf8")
    return _dump_int(len(data_bytes), mt=3) + data_bytes


_SERIALIZERS: Sequence[tuple[type | UnionType, Callable[[Any], bytes]]] = [
    (bool, _dump_bool),
    (int, _dump_int),
    (str, _dump_text),
    (Buffer, _dump_bytes),
    (Mapping, _dump_dict),
    (Sequence, _dump_list),
]


def _load_int(ai: int, data: bytes) -> tuple[int, bytes]:
    if ai < 24:
        return ai, data
    elif ai == 24:
        return data[0], data[1:]
    elif ai == 25:
        return struct.unpack_from(">H", data)[0], data[2:]
    elif ai == 26:
        return struct.unpack_from(">I", data)[0], data[4:]
    elif ai == 27:
        return struct.unpack_from(">Q", data)[0], data[8:]
    raise ValueError("Invalid additional information")


def _load_nint(ai: int, data: bytes) -> tuple[int, bytes]:
    val, rest = _load_int(ai, data)
    return -1 - val, rest


def _load_bool(ai: int, data: bytes) -> tuple[bool, bytes]:
    return ai == 21, data


def _load_bytes(ai: int, data: bytes) -> tuple[bytes, bytes]:
    ln, data = _load_int(ai, data)
    return data[:ln], data[ln:]


def _load_text(ai: int, data: bytes) -> tuple[str, bytes]:
    enc, rest = _load_bytes(ai, data)
    return enc.decode("utf8"), rest


def _load_array(ai: int, data: bytes) -> tuple[Sequence[CborType], bytes]:
    ln, data = _load_int(ai, data)
    values = []
    for i in range(ln):
        val, data = decode_from(data)
        values.append(val)
    return values, data


def _load_map(ai: int, data: bytes) -> tuple[Mapping[CborType, CborType], bytes]:
    ln, data = _load_int(ai, data)
    values = {}
    for i in range(ln):
        k, data = decode_from(data)
        v, data = decode_from(data)
        values[k] = v
    return values, data


_DESERIALIZERS = {
    0: _load_int,
    1: _load_nint,
    2: _load_bytes,
    3: _load_text,
    4: _load_array,
    5: _load_map,
    7: _load_bool,
}


def encode(data: CborType) -> bytes:
    """Encodes data to a CBOR byte string."""
    for k, v in _SERIALIZERS:
        if isinstance(data, k):
            return v(data)
    raise ValueError(f"Unsupported value: {data!r}")


def decode_from(data: bytes) -> tuple[Any, bytes]:
    """Decodes a CBOR-encoded value from the start of a byte string.

    Additional data after a valid CBOR object is returned as well.

    :return: The decoded object, and any remaining data."""
    fb = data[0]
    return _DESERIALIZERS[fb >> 5](fb & 0b11111, data[1:])


def decode(data) -> CborType:
    """Decodes data from a CBOR-encoded byte string.

    Also validates that no extra data follows the encoded object.
    """
    value, rest = decode_from(data)
    if rest != b"":
        raise ValueError("Extraneous data")
    return value
