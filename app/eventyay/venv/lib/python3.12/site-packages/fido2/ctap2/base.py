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

import logging
import struct
from dataclasses import Field, dataclass, field, fields
from enum import IntEnum, unique
from threading import Event
from typing import Any, Callable, Mapping, cast

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .. import cbor
from ..cose import CoseKey
from ..ctap import CtapDevice, CtapError
from ..hid import CAPABILITY, CTAPHID
from ..utils import _DataClassMapping
from ..webauthn import Aaguid, AuthenticatorData

logger = logging.getLogger(__name__)


def args(*params) -> dict[int, Any]:
    """Constructs a dict from a list of arguments for sending a CBOR command.
    None elements will be omitted.

    :param params: Arguments, in order, to add to the command.
    :return: The input parameters as a dict.
    """
    return {i: v for i, v in enumerate(params, 1) if v is not None}


class _CborDataObject(_DataClassMapping[int]):
    @classmethod
    def _get_field_key(cls, field: Field) -> int:
        return fields(cls).index(field) + 1  # type: ignore


@dataclass(eq=False, frozen=True)
class Info(_CborDataObject):
    """Binary CBOR encoded response data returned by the CTAP2 GET_INFO command.

    See:
    https://fidoalliance.org/specs/fido-v2.2-rd-20230321/fido-client-to-authenticator-protocol-v2.2-rd-20230321.html#authenticatorGetInfo
    for descriptions of these fields.

    Note that while many fields are optional when returned by the authenticator,
    this dataclass uses defaults to represent a missing value such as empty lists
    or dicts, or the integer value 0. These are used rather than None for omitted
    values as long as this can be done without introducing any practical ambiguity.
    This also means that several of these fields may have a 0 value even if the
    specification states that they should be non-zero when returned from the
    authenticator.

    :param _: The binary content of the Info data.
    """

    versions: list[str]
    extensions: list[str] = field(default_factory=list)
    aaguid: Aaguid = Aaguid.NONE
    options: dict[str, bool] = field(default_factory=dict)
    max_msg_size: int = 1024
    pin_uv_protocols: list[int] = field(default_factory=list)
    max_creds_in_list: int = 0
    max_cred_id_length: int = 0
    transports: list[str] = field(default_factory=list)
    algorithms: list[dict[str, Any]] = field(default_factory=list)
    max_large_blob: int = 0
    force_pin_change: bool = False
    min_pin_length: int = 4
    firmware_version: int = 0
    max_cred_blob_length: int = 0
    max_rpids_for_min_pin: int = 0
    preferred_platform_uv_attempts: int = 0
    uv_modality: int = 0
    certifications: dict = field(default_factory=dict)
    remaining_disc_creds: int | None = None
    vendor_prototype_config_commands: list[int] = field(default_factory=list)
    attestation_formats: list[str] = field(default_factory=lambda: ["packed"])
    uv_count_since_pin: int | None = None
    long_touch_for_reset: bool = False
    enc_identifier: bytes | None = None
    transports_for_reset: list[str] = field(default_factory=list)
    pin_complexity_policy: bool | None = None
    pin_complexity_policy_url: bytes | None = None
    max_pin_length: int = 63
    enc_cred_store_state: bytes | None = None
    authenticator_config_commands: list[int] | None = None

    def _decrypt(
        self, encrypted: bytes | None, info: bytes, pin_token: bytes
    ) -> bytes | None:
        if not encrypted:
            return None

        iv, ct = encrypted[:16], encrypted[16:]
        be = default_backend()
        secret = HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=b"\0" * 32,
            info=info,
            backend=be,
        ).derive(pin_token)

        dec = Cipher(algorithms.AES(secret), modes.CBC(iv), be).decryptor()
        return dec.update(ct) + dec.finalize()

    def get_identifier(self, pin_token: bytes) -> bytes | None:
        """Decrypt the device identifier using a persistent PUAT."""
        return self._decrypt(self.enc_identifier, b"encIdentifier", pin_token)

    def get_cred_store_state(self, pin_token: bytes) -> bytes | None:
        """Decrypt the credential store state using a persistent PUAT."""
        return self._decrypt(self.enc_cred_store_state, b"encCredStoreState", pin_token)


@dataclass(eq=False, frozen=True)
class AttestationResponse(_CborDataObject):
    """Binary CBOR encoded attestation object.

    :param _: The binary representation of the attestation object.
    :ivar fmt: The type of attestation used.
    :ivar auth_data: The attested authenticator data.
    :ivar att_stmt: The attestation statement.
    :ivar ep_att: Whether an enterprise attestation was returned for this credential.
    :ivar large_blob_key: The largeBlobKey for the credential, if requested.
    :ivar unsigned_extension_outputs: Any unsigned outputs of extensions.
    """

    fmt: str
    auth_data: AuthenticatorData
    att_stmt: dict[str, Any]
    ep_att: bool | None = None
    large_blob_key: bytes | None = None
    unsigned_extension_outputs: dict[str, Any] = field(default_factory=dict)


@dataclass(eq=False, frozen=True)
class AssertionResponse(_CborDataObject):
    """Binary CBOR encoded assertion response.

    :param _: The binary representation of the assertion response.
    :ivar credential: The credential used for the assertion.
    :ivar auth_data: The authenticator data part of the response.
    :ivar signature: The digital signature of the assertion.
    :ivar user: The user data of the credential.
    :ivar number_of_credentials: The total number of responses available
        (only set for the first response, if > 1).
    """

    credential: Mapping[str, Any]
    auth_data: AuthenticatorData
    signature: bytes
    user: dict[str, Any] | None = None
    number_of_credentials: int | None = None
    user_selected: bool | None = None
    large_blob_key: bytes | None = None

    def verify(self, client_param: bytes, public_key: CoseKey):
        """Verify the digital signature of the response with regard to the
        client_param, using the given public key.

        :param client_param: SHA256 hash of the ClientData used for the request.
        :param public_key: The public key of the credential, to verify.
        """
        public_key.verify(self.auth_data + client_param, self.signature)

    @classmethod
    def from_ctap1(
        cls, app_param: bytes, credential: Mapping[str, Any], authentication
    ) -> "AssertionResponse":
        """Create an AssertionResponse from a CTAP1 SignatureData instance.

        :param app_param: SHA256 hash of the RP ID used for the CTAP1 request.
        :param credential: Credential used for the CTAP1 request (from the
            allowList).
        :param authentication: The CTAP1 signature data.
        :return: The assertion response.
        """
        return cls(
            credential=credential,
            auth_data=AuthenticatorData.create(
                app_param,
                authentication.user_presence & AuthenticatorData.FLAG.UP,
                authentication.counter,
            ),
            signature=authentication.signature,
        )


class Ctap2:
    """Implementation of the CTAP2 specification.

    :param device: A CtapHidDevice handle supporting CTAP2.
    :param strict_cbor: Validate that CBOR returned from the Authenticator is
        canonical, defaults to True.
    """

    @unique
    class CMD(IntEnum):
        MAKE_CREDENTIAL = 0x01
        GET_ASSERTION = 0x02
        GET_INFO = 0x04
        CLIENT_PIN = 0x06
        RESET = 0x07
        GET_NEXT_ASSERTION = 0x08
        BIO_ENROLLMENT = 0x09
        CREDENTIAL_MGMT = 0x0A
        SELECTION = 0x0B
        LARGE_BLOBS = 0x0C
        CONFIG = 0x0D

        BIO_ENROLLMENT_PRE = 0x40
        CREDENTIAL_MGMT_PRE = 0x41

    def __init__(self, device: CtapDevice, strict_cbor: bool = True):
        if not device.capabilities & CAPABILITY.CBOR:
            raise ValueError("Device does not support CTAP2.")
        self.device = device
        self._strict_cbor = strict_cbor
        self._max_msg_size = 1024  # For initial get_info call
        self._info = self.get_info()
        self._max_msg_size = self._info.max_msg_size

    @property
    def info(self) -> Info:
        """Get a cached Info object which can be used to determine capabilities.

        :rtype: Info
        :return: The response of calling GetAuthenticatorInfo.
        """
        return self._info

    def send_cbor(
        self,
        cmd: int,
        data: Mapping[int, Any] | None = None,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> Mapping[int, Any]:
        """Sends a CBOR message to the device, and waits for a response.

        :param cmd: The command byte of the request.
        :param data: The payload to send (to be CBOR encoded).
        :param event: Optional threading.Event used to cancel the request.
        :param on_keepalive: Optional function called when keep-alive is sent by
            the authenticator.
        """
        request = struct.pack(">B", cmd)
        if data is not None:
            request += cbor.encode(data)
        if len(request) > self._max_msg_size:
            raise CtapError(CtapError.ERR.REQUEST_TOO_LARGE)
        response = self.device.call(CTAPHID.CBOR, request, event, on_keepalive)
        status = response[0]
        if status != 0x00:
            raise CtapError(status)
        enc = response[1:]
        if not enc:
            return {}
        decoded = cbor.decode(enc)
        if self._strict_cbor:
            expected = cbor.encode(decoded)
            if expected != enc:
                raise ValueError(
                    "Non-canonical CBOR from Authenticator.\n"
                    f"Got: {enc.hex()}\nExpected: {expected.hex()}"
                )
        if isinstance(decoded, Mapping):
            return cast(Mapping[int, Any], decoded)
        raise TypeError("Decoded value of wrong type")

    def get_info(self) -> Info:
        """CTAP2 getInfo command.

        :return: Information about the authenticator.
        """
        return Info.from_dict(self.send_cbor(Ctap2.CMD.GET_INFO))

    def client_pin(
        self,
        pin_uv_protocol: int,
        sub_cmd: int,
        key_agreement: Mapping[int, Any] | None = None,
        pin_uv_param: bytes | None = None,
        new_pin_enc: bytes | None = None,
        pin_hash_enc: bytes | None = None,
        permissions: int | None = None,
        permissions_rpid: str | None = None,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> Mapping[int, Any]:
        """CTAP2 clientPin command, used for various PIN operations.

        This method is not intended to be called directly. It is intended to be used by
        an instance of the PinProtocolV1 class.

        :param pin_uv_protocol: The PIN/UV protocol version to use.
        :param sub_cmd: A clientPin sub command.
        :param key_agreement: The keyAgreement parameter.
        :param pin_uv_param: The pinAuth parameter.
        :param new_pin_enc: The newPinEnc parameter.
        :param pin_hash_enc: The pinHashEnc parameter.
        :param permissions: The permissions parameter.
        :param permissions_rpid: The permissions RPID parameter.
        :param event: Optional threading.Event used to cancel the request.
        :param on_keepalive: Optional callback function to handle keep-alive
            messages from the authenticator.
        :return: The response of the command, decoded.
        """
        return self.send_cbor(
            Ctap2.CMD.CLIENT_PIN,
            args(
                pin_uv_protocol,
                sub_cmd,
                key_agreement,
                pin_uv_param,
                new_pin_enc,
                pin_hash_enc,
                None,
                None,
                permissions,
                permissions_rpid,
            ),
            event=event,
            on_keepalive=on_keepalive,
        )

    def reset(
        self,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> None:
        """CTAP2 reset command, erases all credentials and PIN.

        :param event: Optional threading.Event object used to cancel the request.
        :param on_keepalive: Optional callback function to handle keep-alive
            messages from the authenticator.
        """
        self.send_cbor(Ctap2.CMD.RESET, event=event, on_keepalive=on_keepalive)
        logger.info("Reset completed - All data erased")

    def make_credential(
        self,
        client_data_hash: bytes,
        rp: Mapping[str, Any],
        user: Mapping[str, Any],
        key_params: list[Mapping[str, Any]],
        exclude_list: list[Mapping[str, Any]] | None = None,
        extensions: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
        pin_uv_param: bytes | None = None,
        pin_uv_protocol: int | None = None,
        enterprise_attestation: int | None = None,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> AttestationResponse:
        """CTAP2 makeCredential operation.

        :param client_data_hash: SHA256 hash of the ClientData.
        :param rp: PublicKeyCredentialRpEntity parameters.
        :param user: PublicKeyCredentialUserEntity parameters.
        :param key_params: List of acceptable credential types.
        :param exclude_list: Optional list of PublicKeyCredentialDescriptors.
        :param extensions: Optional dict of extensions.
        :param options: Optional dict of options.
        :param pin_uv_param: Optional PIN/UV auth parameter.
        :param pin_uv_protocol: The version of PIN/UV protocol used, if any.
        :param enterprise_attestation: Whether or not to request Enterprise Attestation.
        :param event: Optional threading.Event used to cancel the request.
        :param on_keepalive: Optional callback function to handle keep-alive
            messages from the authenticator.
        :return: The new credential.
        """
        logger.debug("Calling CTAP2 make_credential")
        return AttestationResponse.from_dict(
            self.send_cbor(
                Ctap2.CMD.MAKE_CREDENTIAL,
                args(
                    client_data_hash,
                    rp,
                    user,
                    key_params,
                    exclude_list,
                    extensions,
                    options,
                    pin_uv_param,
                    pin_uv_protocol,
                    enterprise_attestation,
                ),
                event=event,
                on_keepalive=on_keepalive,
            )
        )

    def get_assertion(
        self,
        rp_id: str,
        client_data_hash: bytes,
        allow_list: list[Mapping[str, Any]] | None = None,
        extensions: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
        pin_uv_param: bytes | None = None,
        pin_uv_protocol: int | None = None,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> AssertionResponse:
        """CTAP2 getAssertion command.

        :param rp_id: The RP ID of the credential.
        :param client_data_hash: SHA256 hash of the ClientData used.
        :param allow_list: Optional list of PublicKeyCredentialDescriptors.
        :param extensions: Optional dict of extensions.
        :param options: Optional dict of options.
        :param pin_uv_param: Optional PIN/UV auth parameter.
        :param pin_uv_protocol: The version of PIN/UV protocol used, if any.
        :param event: Optional threading.Event used to cancel the request.
        :param on_keepalive: Optional callback function to handle keep-alive messages
            from the authenticator.
        :return: The new assertion.
        """
        logger.debug("Calling CTAP2 get_assertion")
        return AssertionResponse.from_dict(
            self.send_cbor(
                Ctap2.CMD.GET_ASSERTION,
                args(
                    rp_id,
                    client_data_hash,
                    allow_list,
                    extensions,
                    options,
                    pin_uv_param,
                    pin_uv_protocol,
                ),
                event=event,
                on_keepalive=on_keepalive,
            )
        )

    def get_next_assertion(self) -> AssertionResponse:
        """CTAP2 getNextAssertion command.

        :return: The next available assertion response.
        """
        return AssertionResponse.from_dict(self.send_cbor(Ctap2.CMD.GET_NEXT_ASSERTION))

    def get_assertions(self, *args, **kwargs) -> list[AssertionResponse]:
        """Convenience method to get list of assertions.

        See get_assertion and get_next_assertion for details.
        """
        first = self.get_assertion(*args, **kwargs)
        rest = [
            self.get_next_assertion()
            for _ in range(1, first.number_of_credentials or 1)
        ]
        return [first] + rest

    def credential_mgmt(
        self,
        sub_cmd: int,
        sub_cmd_params: Mapping[int, Any] | None = None,
        pin_uv_protocol: int | None = None,
        pin_uv_param: bytes | None = None,
    ) -> Mapping[int, Any]:
        """CTAP2 credentialManagement command, used to manage resident
        credentials.

        NOTE: This implements the current draft version of the CTAP2 specification and
        should be considered highly experimental.

        This method is not intended to be called directly. It is intended to be used by
        an instance of the CredentialManagement class.

        :param sub_cmd: A CredentialManagement sub command.
        :param sub_cmd_params: Sub command specific parameters.
        :param pin_uv_protocol: PIN/UV auth protocol version used.
        :param pin_uv_param: PIN/UV Auth parameter.
        """
        if "credMgmt" in self.info.options:
            cmd = Ctap2.CMD.CREDENTIAL_MGMT
        elif "credentialMgmtPreview" in self.info.options:
            cmd = Ctap2.CMD.CREDENTIAL_MGMT_PRE
        else:
            raise ValueError(
                "Credential Management not supported by this Authenticator"
            )
        return self.send_cbor(
            cmd,
            args(sub_cmd, sub_cmd_params, pin_uv_protocol, pin_uv_param),
        )

    def bio_enrollment(
        self,
        modality: int | None = None,
        sub_cmd: int | None = None,
        sub_cmd_params: Mapping[int, Any] | None = None,
        pin_uv_protocol: int | None = None,
        pin_uv_param: bytes | None = None,
        get_modality: bool | None = None,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> Mapping[int, Any]:
        """CTAP2 bio enrollment command. Used to provision/enumerate/delete bio
        enrollments in the authenticator.

        NOTE: This implements the current draft version of the CTAP2 specification and
        should be considered highly experimental.

        This method is not intended to be called directly. It is intended to be used by
        an instance of the BioEnrollment class.

        :param modality: The user verification modality being used.
        :param sub_cmd: A BioEnrollment sub command.
        :param sub_cmd_params: Sub command specific parameters.
        :param pin_uv_protocol: PIN/UV protocol version used.
        :param pin_uv_param: PIN/UV auth param.
        :param get_modality: Get the user verification type modality.
        """
        if "bioEnroll" in self.info.options:
            cmd = Ctap2.CMD.BIO_ENROLLMENT
        elif "userVerificationMgmtPreview" in self.info.options:
            cmd = Ctap2.CMD.BIO_ENROLLMENT_PRE
        else:
            raise ValueError("Authenticator does not support Bio Enroll")
        return self.send_cbor(
            cmd,
            args(
                modality,
                sub_cmd,
                sub_cmd_params,
                pin_uv_protocol,
                pin_uv_param,
                get_modality,
            ),
            event=event,
            on_keepalive=on_keepalive,
        )

    def selection(
        self,
        *,
        event: Event | None = None,
        on_keepalive: Callable[[int], None] | None = None,
    ) -> None:
        """CTAP2 authenticator selection command.

        This command allows the platform to let a user select a certain authenticator
        by asking for user presence.

        :param event: Optional threading.Event used to cancel the request.
        :param on_keepalive: Optional callback function to handle keep-alive messages
            from the authenticator.
        """
        self.send_cbor(Ctap2.CMD.SELECTION, event=event, on_keepalive=on_keepalive)

    def large_blobs(
        self,
        offset: int,
        get: int | None = None,
        set: bytes | None = None,
        length: int | None = None,
        pin_uv_param: bytes | None = None,
        pin_uv_protocol: int | None = None,
    ) -> Mapping[int, Any]:
        """CTAP2 authenticator large blobs command.

        This command is used to read and write the large blob array.

        This method is not intended to be called directly. It is intended to be used by
        an instance of the LargeBlobs class.

        :param offset: The offset of where to start reading/writing data.
        :param get: Optional (max) length of data to read.
        :param set: Optional data to write.
        :param length: Length of the payload in set.
        :param pin_uv_protocol: PIN/UV protocol version used.
        :param pin_uv_param: PIN/UV auth param.
        """
        return self.send_cbor(
            Ctap2.CMD.LARGE_BLOBS,
            args(get, set, offset, length, pin_uv_param, pin_uv_protocol),
        )

    def config(
        self,
        sub_cmd: int,
        sub_cmd_params: Mapping[int, Any] | None = None,
        pin_uv_protocol: int | None = None,
        pin_uv_param: bytes | None = None,
    ) -> Mapping[int, Any]:
        """CTAP2 authenticator config command.

        This command is used to configure various authenticator features through the
        use of its subcommands.

        This method is not intended to be called directly. It is intended to be used by
        an instance of the Config class.

        :param sub_cmd: A Config sub command.
        :param sub_cmd_params: Sub command specific parameters.
        :param pin_uv_protocol: PIN/UV auth protocol version used.
        :param pin_uv_param: PIN/UV Auth parameter.
        """
        return self.send_cbor(
            Ctap2.CMD.CONFIG,
            args(sub_cmd, sub_cmd_params, pin_uv_protocol, pin_uv_param),
        )
