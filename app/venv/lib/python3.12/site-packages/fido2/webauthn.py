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

import json
import struct
from dataclasses import dataclass, field
from enum import Enum, EnumMeta, IntFlag, unique
from typing import Any, Mapping, Sequence, cast

from . import cbor
from .cose import ES256, CoseKey
from .utils import (
    ByteBuffer,
    _JsonDataObject,
    sha256,
    websafe_decode,
    websafe_encode,
)

"""
Data classes based on the W3C WebAuthn specification (https://www.w3.org/TR/webauthn/).

See the specification for a description and details on their usage.

Most of these classes can be serialized to JSON-compatible dictionaries by passing them
to dict(), and then deserialized by calling DataClass.from_dict(data). For example:

    user = PublicKeyCredentialUserEntity(id=b"1234", name="Alice")
    data = dict(user)
    # data is now a JSON-compatible dictionary, json.dumps(data) will work
    user2 = PublicKeyCredentialUserEntity.from_dict(data)
    assert user == user2
"""

# Binary types


class Aaguid(bytes):
    def __init__(self, data: bytes):
        if len(self) != 16:
            raise ValueError("AAGUID must be 16 bytes")

    def __bool__(self):
        return self != Aaguid.NONE

    def __str__(self):
        h = self.hex()
        return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

    def __repr__(self):
        return f"AAGUID({str(self)})"

    @classmethod
    def parse(cls, value: str) -> Aaguid:
        return cls.fromhex(value.replace("-", ""))

    NONE: Aaguid


# Special instance of AAGUID used when there is no AAGUID
Aaguid.NONE = Aaguid(b"\0" * 16)


@dataclass(init=False, frozen=True)
class AttestedCredentialData(bytes):
    aaguid: Aaguid
    credential_id: bytes
    public_key: CoseKey

    def __init__(self, _: bytes):
        super().__init__()

        parsed = AttestedCredentialData._parse(self)
        object.__setattr__(self, "aaguid", parsed[0])
        object.__setattr__(self, "credential_id", parsed[1])
        object.__setattr__(self, "public_key", parsed[2])
        if parsed[3]:
            raise ValueError("Wrong length")

    def __str__(self):  # Override default implementation from bytes.
        return repr(self)

    @staticmethod
    def _parse(data: bytes) -> tuple[bytes, bytes, CoseKey, bytes]:
        """Parse the components of an AttestedCredentialData from a binary
        string, and return them.

        :param data: A binary string containing an attested credential data.
        :return: AAGUID, credential ID, public key, and remaining data.
        """
        reader = ByteBuffer(data)
        aaguid = Aaguid(reader.read(16))
        cred_id = reader.read(reader.unpack(">H"))
        pub_key, rest = cbor.decode_from(reader.read())
        return aaguid, cred_id, CoseKey.parse(pub_key), rest

    @classmethod
    def create(
        cls, aaguid: bytes, credential_id: bytes, public_key: CoseKey
    ) -> AttestedCredentialData:
        """Create an AttestedCredentialData by providing its components.

        :param aaguid: The AAGUID of the authenticator.
        :param credential_id: The binary ID of the credential.
        :param public_key: A COSE formatted public key.
        :return: The attested credential data.
        """
        return cls(
            aaguid
            + struct.pack(">H", len(credential_id))
            + credential_id
            + cbor.encode(public_key)
        )

    @classmethod
    def unpack_from(cls, data: bytes) -> tuple[AttestedCredentialData, bytes]:
        """Unpack an AttestedCredentialData from a byte string, returning it and
        any remaining data.

        :param data: A binary string containing an attested credential data.
        :return: The parsed AttestedCredentialData, and any remaining data from
            the input.
        """
        aaguid, cred_id, pub_key, rest = cls._parse(data)
        return cls.create(aaguid, cred_id, pub_key), rest

    @classmethod
    def from_ctap1(cls, key_handle: bytes, public_key: bytes) -> AttestedCredentialData:
        """Create an AttestatedCredentialData from a CTAP1 RegistrationData instance.

        :param key_handle: The CTAP1 credential key_handle.
        :type key_handle: bytes
        :param public_key: The CTAP1 65 byte public key.
        :type public_key: bytes
        :return: The credential data, using an all-zero AAGUID.
        :rtype: AttestedCredentialData
        """
        return cls.create(Aaguid.NONE, key_handle, ES256.from_ctap1(public_key))


@dataclass(init=False, frozen=True)
class AuthenticatorData(bytes):
    """Binary encoding of the authenticator data.

    :param _: The binary representation of the authenticator data.
    :ivar rp_id_hash: SHA256 hash of the RP ID.
    :ivar flags: The flags of the authenticator data, see
        AuthenticatorData.FLAG.
    :ivar counter: The signature counter of the authenticator.
    :ivar credential_data: Attested credential data, if available.
    :ivar extensions: Authenticator extensions, if available.
    """

    class FLAG(IntFlag):
        """Authenticator data flags

        See https://www.w3.org/TR/webauthn/#sec-authenticator-data for details
        """

        # Names used in WebAuthn
        UP = 0x01
        UV = 0x04
        BE = 0x08
        BS = 0x10
        AT = 0x40
        ED = 0x80

        # Aliases (for historical purposes)
        USER_PRESENT = 0x01
        USER_VERIFIED = 0x04
        BACKUP_ELIGIBILITY = 0x08
        BACKUP_STATE = 0x10
        ATTESTED = 0x40
        EXTENSION_DATA = 0x80

    rp_id_hash: bytes
    flags: AuthenticatorData.FLAG
    counter: int
    credential_data: AttestedCredentialData | None
    extensions: Mapping | None

    def __init__(self, _: bytes):
        super().__init__()

        reader = ByteBuffer(self)
        object.__setattr__(self, "rp_id_hash", reader.read(32))
        object.__setattr__(self, "flags", reader.unpack("B"))
        object.__setattr__(self, "counter", reader.unpack(">I"))
        rest = reader.read()

        if self.flags & AuthenticatorData.FLAG.AT:
            credential_data, rest = AttestedCredentialData.unpack_from(rest)
        else:
            credential_data = None
        object.__setattr__(self, "credential_data", credential_data)

        if self.flags & AuthenticatorData.FLAG.ED:
            extensions, rest = cbor.decode_from(rest)
        else:
            extensions = None
        object.__setattr__(self, "extensions", extensions)

        if rest:
            raise ValueError("Wrong length")

    def __str__(self):  # Override default implementation from bytes.
        return repr(self)

    @classmethod
    def create(
        cls,
        rp_id_hash: bytes,
        flags: AuthenticatorData.FLAG,
        counter: int,
        credential_data: bytes = b"",
        extensions: Mapping | None = None,
    ):
        """Create an AuthenticatorData instance.

        :param rp_id_hash: SHA256 hash of the RP ID.
        :param flags: Flags of the AuthenticatorData.
        :param counter: Signature counter of the authenticator data.
        :param credential_data: Authenticated credential data (only if attested
            credential data flag is set).
        :param extensions: Authenticator extensions (only if ED flag is set).
        :return: The authenticator data.
        """
        return cls(
            rp_id_hash
            + struct.pack(">BI", flags, counter)
            + credential_data
            + (cbor.encode(extensions) if extensions is not None else b"")
        )

    def is_user_present(self) -> bool:
        """Return true if the User Present flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.UP)

    def is_user_verified(self) -> bool:
        """Return true if the User Verified flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.UV)

    def is_backup_eligible(self) -> bool:
        """Return true if the Backup Eligibility flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.BE)

    def is_backed_up(self) -> bool:
        """Return true if the Backup State flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.BS)

    def is_attested(self) -> bool:
        """Return true if the Attested credential data flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.AT)

    def has_extension_data(self) -> bool:
        """Return true if the Extenstion data flag is set."""
        return bool(self.flags & AuthenticatorData.FLAG.ED)


@dataclass(init=False, frozen=True)
class AttestationObject(bytes):  # , Mapping[str, Any]):
    """Binary CBOR encoded attestation object.

    :param _: The binary representation of the attestation object.
    :ivar fmt: The type of attestation used.
    :ivar auth_data: The attested authenticator data.
    :ivar att_statement: The attestation statement.
    """

    fmt: str
    auth_data: AuthenticatorData
    att_stmt: Mapping[str, Any]

    def __init__(self, _: bytes):
        super().__init__()

        data = cast(Mapping[str, Any], cbor.decode(bytes(self)))
        object.__setattr__(self, "fmt", data["fmt"])
        object.__setattr__(self, "auth_data", AuthenticatorData(data["authData"]))
        object.__setattr__(self, "att_stmt", data["attStmt"])

    def __str__(self):  # Override default implementation from bytes.
        return repr(self)

    @classmethod
    def create(
        cls, fmt: str, auth_data: AuthenticatorData, att_stmt: Mapping[str, Any]
    ) -> AttestationObject:
        return cls(
            cbor.encode({"fmt": fmt, "authData": auth_data, "attStmt": att_stmt})
        )

    @classmethod
    def from_ctap1(cls, app_param: bytes, registration) -> AttestationObject:
        """Create an AttestationObject from a CTAP1 RegistrationData instance.

        :param app_param: SHA256 hash of the RP ID used for the CTAP1 request.
        :type app_param: bytes
        :param registration: The CTAP1 registration data.
        :type registration: RegistrationData
        :return: The attestation object, using the "fido-u2f" format.
        :rtype: AttestationObject
        """
        return cls.create(
            "fido-u2f",
            AuthenticatorData.create(
                app_param,
                AuthenticatorData.FLAG.AT | AuthenticatorData.FLAG.UP,
                0,
                AttestedCredentialData.from_ctap1(
                    registration.key_handle, registration.public_key
                ),
            ),
            {"x5c": [registration.certificate], "sig": registration.signature},
        )


@dataclass(init=False, frozen=True)
class CollectedClientData(bytes):
    @unique
    class TYPE(str, Enum):
        CREATE = "webauthn.create"
        GET = "webauthn.get"

    _data: Mapping[str, Any]
    type: str
    challenge: bytes
    origin: str
    cross_origin: bool = False

    def __init__(self, _: bytes):
        super().__init__()

        object.__setattr__(self, "_data", json.loads(self.decode()))
        object.__setattr__(self, "type", self._data["type"])
        object.__setattr__(self, "challenge", websafe_decode(self._data["challenge"]))
        object.__setattr__(self, "origin", self._data["origin"])
        object.__setattr__(self, "cross_origin", self._data.get("crossOrigin", False))

    @classmethod
    def create(
        cls,
        type: str,
        challenge: bytes | str,
        origin: str,
        cross_origin: bool = False,
        **kwargs,
    ) -> CollectedClientData:
        if isinstance(challenge, bytes):
            encoded_challenge = websafe_encode(challenge)
        else:
            encoded_challenge = challenge
        return cls(
            json.dumps(
                {
                    "type": type,
                    "challenge": encoded_challenge,
                    "origin": origin,
                    "crossOrigin": cross_origin,
                    **kwargs,
                },
                separators=(",", ":"),
            ).encode()
        )

    def __str__(self):  # Override default implementation from bytes.
        return repr(self)

    @property
    def b64(self) -> str:
        return websafe_encode(self)

    @property
    def hash(self) -> bytes:
        return sha256(self)


class _StringEnumMeta(EnumMeta):
    def _get_value(cls, value):
        return None

    def __call__(cls, value, *args, **kwargs):  # type: ignore
        try:
            return super().__call__(value, *args, **kwargs)
        except ValueError:
            return cls._get_value(value)


class _StringEnum(str, Enum, metaclass=_StringEnumMeta):
    """Enum of strings for WebAuthn types.

    Unrecognized values are treated as missing.
    """


@unique
class AttestationConveyancePreference(_StringEnum):
    NONE = "none"
    INDIRECT = "indirect"
    DIRECT = "direct"
    ENTERPRISE = "enterprise"


@unique
class UserVerificationRequirement(_StringEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    DISCOURAGED = "discouraged"


@unique
class ResidentKeyRequirement(_StringEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    DISCOURAGED = "discouraged"


@unique
class AuthenticatorAttachment(_StringEnum):
    PLATFORM = "platform"
    CROSS_PLATFORM = "cross-platform"


@unique
class AuthenticatorTransport(_StringEnum):
    USB = "usb"
    NFC = "nfc"
    BLE = "ble"
    HYBRID = "hybrid"
    INTERNAL = "internal"


@unique
class PublicKeyCredentialType(_StringEnum):
    PUBLIC_KEY = "public-key"


@unique
class PublicKeyCredentialHint(_StringEnum):
    SECURITY_KEY = "security-key"
    CLIENT_DEVICE = "client-device"
    HYBRID = "hybrid"


def _as_cbor(data: _JsonDataObject) -> Mapping[str, Any]:
    return {k: super(_JsonDataObject, data).__getitem__(k) for k in data}


@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialRpEntity(_JsonDataObject):
    name: str
    id: str | None = None

    @property
    def id_hash(self) -> bytes | None:
        """Return SHA256 hash of the identifier."""
        return sha256(self.id.encode("utf8")) if self.id else None


# Note that name and display_name are required in the WebAuthn spec, but CTAP2
# allows them to be omitted, so we make them optional here.
@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialUserEntity(_JsonDataObject):
    name: str | None = None
    id: bytes
    display_name: str | None = None


@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialParameters(_JsonDataObject):
    type: PublicKeyCredentialType
    alg: int


@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialDescriptor(_JsonDataObject):
    type: PublicKeyCredentialType
    id: bytes
    transports: Sequence[AuthenticatorTransport] | None = None


@dataclass(eq=False, frozen=True, kw_only=True)
class AuthenticatorSelectionCriteria(_JsonDataObject):
    authenticator_attachment: AuthenticatorAttachment | None = None
    resident_key: ResidentKeyRequirement | None = None
    user_verification: UserVerificationRequirement | None = None
    require_resident_key: bool | None = False

    def __post_init__(self):
        super().__post_init__()

        if self.resident_key is None:
            object.__setattr__(
                self,
                "resident_key",
                (
                    ResidentKeyRequirement.REQUIRED
                    if self.require_resident_key
                    else ResidentKeyRequirement.DISCOURAGED
                ),
            )
        object.__setattr__(
            self,
            "require_resident_key",
            self.resident_key == ResidentKeyRequirement.REQUIRED,
        )


@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialCreationOptions(_JsonDataObject):
    rp: PublicKeyCredentialRpEntity
    user: PublicKeyCredentialUserEntity
    challenge: bytes
    pub_key_cred_params: Sequence[PublicKeyCredentialParameters]
    timeout: int | None = None
    exclude_credentials: Sequence[PublicKeyCredentialDescriptor] | None = None
    authenticator_selection: AuthenticatorSelectionCriteria | None = None
    hints: Sequence[PublicKeyCredentialHint] | None = None
    attestation: AttestationConveyancePreference | None = None
    attestation_formats: Sequence[str] | None = None
    extensions: Mapping[str, Any] | None = None


@dataclass(eq=False, frozen=True, kw_only=True)
class PublicKeyCredentialRequestOptions(_JsonDataObject):
    challenge: bytes
    timeout: int | None = None
    rp_id: str | None = None
    allow_credentials: Sequence[PublicKeyCredentialDescriptor] | None = None
    user_verification: UserVerificationRequirement | None = None
    hints: Sequence[PublicKeyCredentialHint] | None = None
    extensions: Mapping[str, Any] | None = None


@dataclass(eq=False, frozen=True, kw_only=True)
class AuthenticatorAttestationResponse(_JsonDataObject):
    client_data: CollectedClientData = field(metadata=dict(name="clientDataJSON"))
    attestation_object: AttestationObject


@dataclass(eq=False, frozen=True, kw_only=True)
class AuthenticatorAssertionResponse(_JsonDataObject):
    client_data: CollectedClientData = field(metadata=dict(name="clientDataJSON"))
    authenticator_data: AuthenticatorData
    signature: bytes
    user_handle: bytes | None = None


class AuthenticationExtensionsClientOutputs(Mapping[str, Any]):
    """Holds extension output from a call to MakeCredential or GetAssertion.

    When accessed as a dict, all bytes values will be serialized to base64url encoding,
    capable of being serialized to JSON.

    When accessed using attributes, richer types will instead be returned.
    """

    def __init__(self, outputs: Mapping[str, Any] = {}):
        self._members = {k: v for k, v in outputs.items() if v is not None}

    def __iter__(self):
        return iter(self._members)

    def __len__(self):
        return len(self._members)

    def __getitem__(self, key):
        value = self._members[key]
        if isinstance(value, bytes):
            return websafe_encode(value)
        elif isinstance(value, Mapping) and not isinstance(value, dict):
            return dict(value)
        return value

    def __getattr__(self, key):
        parts = key.split("_")
        name = parts[0] + "".join(p.title() for p in parts[1:])
        return self._members.get(name)

    def __repr__(self):
        return repr(dict(self))


@dataclass(eq=False, frozen=True, kw_only=True)
class RegistrationResponse(_JsonDataObject):
    """
    Represents the RegistrationResponse structure from the WebAuthn specification,
    with fields modeled after the JSON serialization.

    Serializing this object to JSON can be done by using json.dumps(dict(response)).

    See: https://www.w3.org/TR/webauthn-3/#dictdef-registrationresponsejson
    """

    id: str = field(init=False)
    raw_id: bytes
    response: AuthenticatorAttestationResponse
    authenticator_attachment: AuthenticatorAttachment | None = None
    client_extension_results: AuthenticationExtensionsClientOutputs = field(
        default_factory=AuthenticationExtensionsClientOutputs
    )
    type: PublicKeyCredentialType = PublicKeyCredentialType.PUBLIC_KEY

    def __post_init__(self):
        object.__setattr__(self, "id", websafe_encode(self.raw_id))
        super().__post_init__()

    @classmethod
    def _parse_value(cls, t, value):
        if t == Mapping[str, Any] | None:
            # Don't convert extension_results
            return value
        return super()._parse_value(t, value)

    @classmethod
    def _parse_from_dict(cls, data):
        if "id" in data:
            data = dict(data)
            credential_id = data.pop("id")
            if credential_id != data["rawId"]:
                raise ValueError("id does not match rawId")

        return super()._parse_from_dict(data)


@dataclass(eq=False, frozen=True, kw_only=True)
class AuthenticationResponse(_JsonDataObject):
    """
    Represents the AuthenticationResponse structure from the WebAuthn specification,
    with fields modeled after the JSON serialization.

    Serializing this object to JSON can be done by using json.dumps(dict(response)).

    See: https://www.w3.org/TR/webauthn-3/#dictdef-authenticationresponsejson
    """

    id: str = field(init=False)
    raw_id: bytes
    response: AuthenticatorAssertionResponse
    authenticator_attachment: AuthenticatorAttachment | None = None
    client_extension_results: AuthenticationExtensionsClientOutputs = field(
        default_factory=AuthenticationExtensionsClientOutputs
    )
    type: PublicKeyCredentialType = PublicKeyCredentialType.PUBLIC_KEY

    def __post_init__(self):
        object.__setattr__(self, "id", websafe_encode(self.raw_id))
        super().__post_init__()

    @classmethod
    def _parse_value(cls, t, value):
        if t == Mapping[str, Any] | None:
            # Don't convert extension_results
            return value
        return super()._parse_value(t, value)

    @classmethod
    def _parse_from_dict(cls, data):
        if "id" in data:
            data = dict(data)
            credential_id = data.pop("id")
            if credential_id != data["rawId"]:
                raise ValueError("id does not match rawId")
        return super()._parse_from_dict(data)


@dataclass(eq=False, frozen=True, kw_only=True)
class CredentialCreationOptions(_JsonDataObject):
    public_key: PublicKeyCredentialCreationOptions


@dataclass(eq=False, frozen=True, kw_only=True)
class CredentialRequestOptions(_JsonDataObject):
    public_key: PublicKeyCredentialRequestOptions
