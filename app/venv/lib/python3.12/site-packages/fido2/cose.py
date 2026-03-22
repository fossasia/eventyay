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

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence, TypeVar

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa

from .utils import bytes2int, int2bytes

if TYPE_CHECKING:
    # This type isn't available on cryptography <40.
    from cryptography.hazmat.primitives.asymmetric.types import PublicKeyTypes


class CoseKey(dict):
    """A COSE formatted public key.

    :param _: The COSE key paramters.
    :cvar ALGORITHM: COSE algorithm identifier.
    """

    ALGORITHM: int = None  # type: ignore

    def verify(self, message: bytes, signature: bytes) -> None:
        """Validates a digital signature over a given message.

        :param message: The message which was signed.
        :param signature: The signature to check.
        """
        raise NotImplementedError("Signature verification not supported.")

    @classmethod
    def from_cryptography_key(
        cls: type[T_CoseKey], public_key: PublicKeyTypes
    ) -> T_CoseKey:
        """Converts a PublicKey object from Cryptography into a COSE key.

        :param public_key: Either an EC or RSA public key.
        :return: A CoseKey.
        """
        raise NotImplementedError("Creation from cryptography not supported.")

    @staticmethod
    def for_alg(alg: int) -> type[CoseKey]:
        """Get a subclass of CoseKey corresponding to an algorithm identifier.

        :param alg: The COSE identifier of the algorithm.
        :return: A CoseKey.
        """

        def find_subclass(base_cls: type[CoseKey]) -> type[CoseKey] | None:
            for cls in base_cls.__subclasses__():
                if cls.ALGORITHM == alg:
                    return cls
                subresult = find_subclass(cls)
                if subresult:
                    return subresult
            return None

        return find_subclass(CoseKey) or UnsupportedKey

    @staticmethod
    def for_name(name: str) -> type[CoseKey]:
        """Get a subclass of CoseKey corresponding to an algorithm identifier.

        :param alg: The COSE identifier of the algorithm.
        :return: A CoseKey.
        """

        def find_subclass(base_cls: type[CoseKey]) -> type[CoseKey] | None:
            for cls in base_cls.__subclasses__():
                if cls.__name__ == name:
                    return cls
                subresult = find_subclass(cls)
                if subresult:
                    return subresult
            return None

        return find_subclass(CoseKey) or UnsupportedKey

    @staticmethod
    def parse(cose: Mapping[int, Any]) -> CoseKey:
        """Create a CoseKey from a dict"""
        alg = cose.get(3)
        if not alg:
            raise ValueError("COSE alg identifier must be provided.")
        return CoseKey.for_alg(alg)(cose)

    @staticmethod
    def supported_algorithms() -> Sequence[int]:
        """Get a list of all supported algorithm identifiers"""
        algs: Sequence[type[CoseKey]] = [
            ES256,
            EdDSA,
            ES384,
            ES512,
            PS256,
            RS256,
            ES256K,
        ]
        return [cls.ALGORITHM for cls in algs]


T_CoseKey = TypeVar("T_CoseKey", bound=CoseKey)


class UnsupportedKey(CoseKey):
    """A COSE key with an unsupported algorithm."""


class ES256(CoseKey):
    ALGORITHM = -7
    _HASH_ALG = hashes.SHA256()

    def verify(self, message, signature):
        if self[-1] != 1:
            raise ValueError("Unsupported elliptic curve")
        ec.EllipticCurvePublicNumbers(
            bytes2int(self[-2]), bytes2int(self[-3]), ec.SECP256R1()
        ).public_key(default_backend()).verify(
            signature, message, ec.ECDSA(self._HASH_ALG)
        )

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ec.EllipticCurvePublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls(
            {
                1: 2,
                3: cls.ALGORITHM,
                -1: 1,
                -2: int2bytes(pn.x, 32),
                -3: int2bytes(pn.y, 32),
            }
        )

    @classmethod
    def from_ctap1(cls, data):
        """Creates an ES256 key from a CTAP1 formatted public key byte string.

        :param data: A 65 byte SECP256R1 public key.
        :return: A ES256 key.
        """
        return cls({1: 2, 3: cls.ALGORITHM, -1: 1, -2: data[1:33], -3: data[33:65]})


class ESP256(ES256):
    # See: https://www.ietf.org/archive/id/draft-ietf-jose-fully-specified-algorithms-10.html#name-elliptic-curve-digital-sign  # noqa:E501
    ALGORITHM = -9


class ES384(CoseKey):
    ALGORITHM = -35
    _HASH_ALG = hashes.SHA384()

    def verify(self, message, signature):
        if self[-1] != 2:
            raise ValueError("Unsupported elliptic curve")
        ec.EllipticCurvePublicNumbers(
            bytes2int(self[-2]), bytes2int(self[-3]), ec.SECP384R1()
        ).public_key(default_backend()).verify(
            signature, message, ec.ECDSA(self._HASH_ALG)
        )

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ec.EllipticCurvePublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls(
            {
                1: 2,
                3: cls.ALGORITHM,
                -1: 2,
                -2: int2bytes(pn.x, 48),
                -3: int2bytes(pn.y, 48),
            }
        )


class ESP384(ES384):
    # See: https://www.ietf.org/archive/id/draft-ietf-jose-fully-specified-algorithms-12.html#name-elliptic-curve-digital-sign  # noqa:E501
    ALGORITHM = -51


class ES512(CoseKey):
    ALGORITHM = -36
    _HASH_ALG = hashes.SHA512()

    def verify(self, message, signature):
        if self[-1] != 3:
            raise ValueError("Unsupported elliptic curve")
        ec.EllipticCurvePublicNumbers(
            bytes2int(self[-2]), bytes2int(self[-3]), ec.SECP521R1()
        ).public_key(default_backend()).verify(
            signature, message, ec.ECDSA(self._HASH_ALG)
        )

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ec.EllipticCurvePublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls(
            {
                1: 2,
                3: cls.ALGORITHM,
                -1: 3,
                -2: int2bytes(pn.x, 66),
                -3: int2bytes(pn.y, 66),
            }
        )


class ESP512(ES512):
    # See: https://www.ietf.org/archive/id/draft-ietf-jose-fully-specified-algorithms-12.html#name-elliptic-curve-digital-sign  # noqa:E501
    ALGORITHM = -52


class RS256(CoseKey):
    ALGORITHM = -257
    _HASH_ALG = hashes.SHA256()

    def verify(self, message, signature):
        rsa.RSAPublicNumbers(bytes2int(self[-2]), bytes2int(self[-1])).public_key(
            default_backend()
        ).verify(signature, message, padding.PKCS1v15(), self._HASH_ALG)

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, rsa.RSAPublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls({1: 3, 3: cls.ALGORITHM, -1: int2bytes(pn.n), -2: int2bytes(pn.e)})


class PS256(CoseKey):
    ALGORITHM = -37
    _HASH_ALG = hashes.SHA256()

    def verify(self, message, signature):
        rsa.RSAPublicNumbers(bytes2int(self[-2]), bytes2int(self[-1])).public_key(
            default_backend()
        ).verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(self._HASH_ALG), salt_length=padding.PSS.MAX_LENGTH
            ),
            self._HASH_ALG,
        )

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, rsa.RSAPublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls({1: 3, 3: cls.ALGORITHM, -1: int2bytes(pn.n), -2: int2bytes(pn.e)})


class EdDSA(CoseKey):
    ALGORITHM = -8

    def verify(self, message, signature):
        if self[-1] != 6:
            raise ValueError("Unsupported elliptic curve")
        ed25519.Ed25519PublicKey.from_public_bytes(self[-2]).verify(signature, message)

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ed25519.Ed25519PublicKey)  # noqa: S101
        return cls(
            {
                1: 1,
                3: cls.ALGORITHM,
                -1: 6,
                -2: public_key.public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                ),
            }
        )


class Ed25519(EdDSA):
    # See: https://www.ietf.org/archive/id/draft-ietf-jose-fully-specified-algorithms-12.html#name-edwards-curve-digital-signa  # noqa:E501
    ALGORITHM = -19


class Ed448(CoseKey):
    # See: https://www.ietf.org/archive/id/draft-ietf-jose-fully-specified-algorithms-12.html#name-edwards-curve-digital-signa  # noqa:E501
    ALGORITHM = -53

    def verify(self, message, signature):
        if self[-1] != 7:
            raise ValueError("Unsupported elliptic curve")
        ed448.Ed448PublicKey.from_public_bytes(self[-2]).verify(signature, message)

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ed448.Ed448PublicKey)  # noqa: S101
        return cls(
            {
                1: 1,
                3: cls.ALGORITHM,
                -1: 7,
                -2: public_key.public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                ),
            }
        )


class RS1(CoseKey):
    ALGORITHM = -65535
    _HASH_ALG = hashes.SHA1()  # noqa: S303

    def verify(self, message, signature):
        rsa.RSAPublicNumbers(bytes2int(self[-2]), bytes2int(self[-1])).public_key(
            default_backend()
        ).verify(signature, message, padding.PKCS1v15(), self._HASH_ALG)

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, rsa.RSAPublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls({1: 3, 3: cls.ALGORITHM, -1: int2bytes(pn.n), -2: int2bytes(pn.e)})


class ES256K(CoseKey):
    ALGORITHM = -47
    _HASH_ALG = hashes.SHA256()

    def verify(self, message, signature):
        if self[-1] != 8:
            raise ValueError("Unsupported elliptic curve")
        ec.EllipticCurvePublicNumbers(
            bytes2int(self[-2]), bytes2int(self[-3]), ec.SECP256K1()
        ).public_key(default_backend()).verify(
            signature, message, ec.ECDSA(self._HASH_ALG)
        )

    @classmethod
    def from_cryptography_key(cls, public_key):
        assert isinstance(public_key, ec.EllipticCurvePublicKey)  # noqa: S101
        pn = public_key.public_numbers()
        return cls(
            {
                1: 2,
                3: cls.ALGORITHM,
                -1: 8,
                -2: int2bytes(pn.x, 32),
                -3: int2bytes(pn.y, 32),
            }
        )
