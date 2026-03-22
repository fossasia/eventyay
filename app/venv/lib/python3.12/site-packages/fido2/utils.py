# Copyright (c) 2013 Yubico AB
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

"""Various utility functions.

This module contains various functions used throughout the rest of the project.
"""

from __future__ import annotations

import struct
from abc import abstractmethod
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import Field, fields
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Hashable,
    Mapping,
    Sequence,
    TypeVar,
    get_type_hints,
    overload,
)

if TYPE_CHECKING:
    import sys

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        # Fallback for Python 3.10 and earlier
        Self = TypeVar("Self", bound="_DataClassMapping")

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac

__all__ = [
    "websafe_encode",
    "websafe_decode",
    "sha256",
    "hmac_sha256",
    "bytes2int",
    "int2bytes",
]


LOG_LEVEL_TRAFFIC = 5


def sha256(data: bytes) -> bytes:
    """Produces a SHA256 hash of the input.

    :param data: The input data to hash.
    :return: The resulting hash.
    """
    h = hashes.Hash(hashes.SHA256(), default_backend())
    h.update(data)
    return h.finalize()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """Performs an HMAC-SHA256 operation on the given data, using the given key.

    :param key: The key to use.
    :param data: The input data to hash.
    :return: The resulting hash.
    """
    h = hmac.HMAC(key, hashes.SHA256(), default_backend())
    h.update(data)
    return h.finalize()


def bytes2int(value: bytes) -> int:
    """Parses an arbitrarily sized integer from a byte string.

    :param value: A byte string encoding a big endian unsigned integer.
    :return: The parsed int.
    """
    return int.from_bytes(value, "big")


def int2bytes(value: int, minlen: int = -1) -> bytes:
    """Encodes an int as a byte string.

    :param value: The integer value to encode.
    :param minlen: An optional minimum length for the resulting byte string.
    :return: The value encoded as a big endian byte string.
    """
    ba = []
    while value > 0xFF:
        ba.append(0xFF & value)
        value >>= 8
    ba.append(value)
    ba.extend([0] * (minlen - len(ba)))
    return bytes(reversed(ba))


def websafe_decode(data: str | bytes) -> bytes:
    """Decodes a websafe-base64 encoded string.
    See: "Base 64 Encoding with URL and Filename Safe Alphabet" from Section 5
    in RFC4648 without padding.

    :param data: The input to decode.
    :return: The decoded bytes.
    """
    if isinstance(data, str):
        data_b = data.encode("ascii")
    else:
        data_b = bytes(data)

    data_b += b"=" * (-len(data_b) % 4)
    return urlsafe_b64decode(data_b)


def websafe_encode(data: bytes) -> str:
    """Encodes a byte string into websafe-base64 encoding.

    :param data: The input to encode.
    :return: The encoded string.
    """
    return urlsafe_b64encode(data).replace(b"=", b"").decode("ascii")


class ByteBuffer(BytesIO):
    """BytesIO-like object with the ability to unpack values."""

    def unpack(self, fmt: str):
        """Reads and unpacks a value from the buffer.

        :param fmt: A struct format string yielding a single value.
        :return: The unpacked value.
        """
        s = struct.Struct(fmt)
        return s.unpack(self.read(s.size))[0]

    def read(self, size: int | None = -1) -> bytes:
        """Like BytesIO.read(), but checks the number of bytes read and raises an error
        if fewer bytes were read than expected.
        """
        data = super().read(size)
        if size is not None and size > 0 and len(data) != size:
            raise ValueError(
                "Not enough data to read (need: %d, had: %d)." % (size, len(data))
            )
        return data


_T = TypeVar("_T", bound=Hashable)


class _DataClassMapping(Mapping[_T, Any]):
    """A data class with members also accessible as a Mapping."""

    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]

    def __post_init__(self):
        hints = get_type_hints(type(self))
        self._field_keys: dict[_T, Field[Any]]
        object.__setattr__(self, "_field_keys", {})

        for f in fields(self):
            self._field_keys[self._get_field_key(f)] = f
            value = getattr(self, f.name)
            if value is not None:
                try:
                    value = self._parse_value(hints[f.name], value)
                    object.__setattr__(self, f.name, value)
                except (TypeError, KeyError, ValueError):
                    raise ValueError(
                        f"Error parsing field {f.name} for {self.__class__.__name__}"
                    )

    @classmethod
    @abstractmethod
    def _get_field_key(cls, field: Field) -> _T:
        raise NotImplementedError()

    def __iter__(self):
        return (
            k for k, f in self._field_keys.items() if getattr(self, f.name) is not None
        )

    def __len__(self):
        return len(list(iter(self)))

    def __getitem__(self, key):
        f = self._field_keys[key]
        value = getattr(self, f.name)
        if value is None:
            raise KeyError(key)
        serialize = f.metadata.get("serialize")
        if serialize:
            return serialize(value)
        if isinstance(value, Mapping) and not isinstance(value, dict):
            return dict(value)
        if isinstance(value, Sequence) and all(isinstance(v, Mapping) for v in value):
            return [v if isinstance(v, dict) else dict(v) for v in value]
        return value

    @classmethod
    def _parse_value(cls, t, value):
        if (t | None) == t:  # Optional, get the type
            t = t.__args__[0]

        # Check if type is already correct
        try:
            if t is Any or isinstance(value, t):
                return value
        except TypeError:
            pass

        # Handle list of values
        if issubclass(getattr(t, "__origin__", object), Sequence):
            t = getattr(t, "__args__")[0]
            return [cls._parse_value(t, v) for v in value]

        # Handle Mappings
        elif issubclass(getattr(t, "__origin__", object), Mapping) and isinstance(
            value, Mapping
        ):
            t_k, t_v = getattr(t, "__args__")
            return {
                cls._parse_value(t_k, k): cls._parse_value(t_v, v)
                for k, v in value.items()
            }

        # Check if type has from_dict
        from_dict = getattr(t, "from_dict", None)
        if from_dict:
            return from_dict(value)

        # Convert to enum values, other wrappers
        wrap = getattr(t, "__call__", None)
        if wrap:
            return wrap(value)

        raise ValueError(f"Unparseable value of type {type(value)} for {t}")

    @overload
    @classmethod
    def from_dict(cls: type[Self], data: None) -> None: ...

    @overload
    @classmethod
    def from_dict(cls: type[Self], data: Self) -> Self: ...

    @overload
    @classmethod
    def from_dict(cls: type[Self], data: Mapping[_T, Any]) -> Self: ...

    @classmethod
    def from_dict(cls, data):
        if data is None:
            return None
        if isinstance(data, cls):
            return data
        if not isinstance(data, Mapping):
            raise TypeError(
                f"{cls.__name__}.from_dict called with non-Mapping data of type"
                f"{type(data)}"
            )
        return cls._parse_from_dict(data)

    @classmethod
    def _parse_from_dict(cls: type[Self], data: Mapping[_T, Any]) -> Self:
        kwargs = {}
        hints = get_type_hints(cls)
        for f in fields(cls):
            key = cls._get_field_key(f)
            value = data.get(key)
            if value is None:
                continue
            deserialize = f.metadata.get("deserialize")
            if deserialize:
                value = deserialize(value)
            else:
                t = hints[f.name]
                value = cls._parse_value(t, value)

            kwargs[f.name] = value
        return cls(**kwargs)


class _JsonDataObject(_DataClassMapping[str]):
    """A data class with members also accessible as a JSON-serializable Mapping."""

    @classmethod
    def _get_field_key(cls, field: Field) -> str:
        name = field.metadata.get("name")
        if name:
            return name
        parts = field.name.split("_")
        return parts[0] + "".join(p.title() for p in parts[1:])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(value, bytes):
            return websafe_encode(value)
        return value

    @classmethod
    def _parse_value(cls, t, value):
        if (t | None) == t:  # Optional, get the type
            t2 = t.__args__[0]
        else:
            t2 = t
        # bytes are encoded as websafe_b64 strings
        if isinstance(t2, type) and issubclass(t2, bytes) and isinstance(value, str):
            return websafe_decode(value)

        return super()._parse_value(t, value)
