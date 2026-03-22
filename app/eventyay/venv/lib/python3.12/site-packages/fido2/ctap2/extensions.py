# Copyright (c) 2020 Yubico AB
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

import abc
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Mapping, cast

from ..utils import _JsonDataObject, sha256, websafe_encode
from ..webauthn import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRequestOptions,
    ResidentKeyRequirement,
)
from .base import AssertionResponse, AttestationResponse, Ctap2
from .blob import LargeBlobs
from .pin import ClientPin, PinProtocol


class ExtensionProcessor(abc.ABC):
    """Base class for CTAP2 extension processing.

    See: :class:`RegistrationExtensionProcessor` and
    :class:`AuthenticationExtensionProcessor`.
    """

    def __init__(
        self,
        permissions: ClientPin.PERMISSION = ClientPin.PERMISSION(0),
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ):
        self.permissions = permissions
        self._inputs = inputs
        self._outputs = outputs


class RegistrationExtensionProcessor(ExtensionProcessor):
    """Processing state for a CTAP2 extension, for single use.

    The ExtensionProcessor holds state and logic for client processing of an extension,
    for a registration (MakeCredential) call.

    :param permissions: PinUvAuthToken permissions required by the extension.
    :param inputs: Default authenticator inputs, if prepare_inputs is not overridden.
    :param outputs: Default client outputs, if prepare_outputs is not overridden.
    """

    def prepare_inputs(self, pin_token: bytes | None) -> dict[str, Any] | None:
        "Prepare authenticator extension inputs, to be passed to the Authenenticator."
        return self._inputs

    def prepare_outputs(
        self,
        response: AttestationResponse,
        pin_token: bytes | None,
    ) -> dict[str, Any] | None:
        "Prepare client extension outputs, to be returned to the caller."
        return self._outputs


class AuthenticationExtensionProcessor(ExtensionProcessor):
    """Processing state for a CTAP2 extension, for single use.

    The ExtensionProcessor holds state and logic for client processing of an extension,
    for an authentication (GetAssertion) call.

    :param permissions: PinUvAuthToken permissions required by the extension.
    :param inputs: Default authenticator inputs, if prepare_inputs is not overridden.
    :param outputs: Default client outputs, if prepare_outputs is not overridden.
    """

    def prepare_inputs(
        self,
        selected: PublicKeyCredentialDescriptor | None,
        pin_token: bytes | None,
    ) -> dict[str, Any] | None:
        "Prepare authenticator extension inputs, to be passed to the Authenenticator."
        return self._inputs

    def prepare_outputs(
        self,
        response: AssertionResponse,
        pin_token: bytes | None,
    ) -> dict[str, Any] | None:
        "Prepare client extension outputs, to be returned to the caller."
        return self._outputs


class Ctap2Extension(abc.ABC):
    """Base class for CTAP2 extensions.

    As of python-fido2 1.2 these instances can be used for multiple requests and
    should be invoked via the make_credential and get_assertion methods.
    Subclasses are instantiated for a single request, if the Authenticator supports
    the extension.
    """

    @abc.abstractmethod
    def is_supported(self, ctap: Ctap2) -> bool:
        """Whether or not the extension is supported by the authenticator."""

    def make_credential(
        self,
        ctap: Ctap2,
        options: PublicKeyCredentialCreationOptions,
        pin_protocol: PinProtocol | None,
    ) -> RegistrationExtensionProcessor | None:
        """Start client extension processing for registration."""
        return None

    def get_assertion(
        self,
        ctap: Ctap2,
        options: PublicKeyCredentialRequestOptions,
        pin_protocol: PinProtocol | None,
    ) -> AuthenticationExtensionProcessor | None:
        """Start client extension processing for authentication."""
        return None


@dataclass(eq=False, frozen=True)
class HMACGetSecretInput(_JsonDataObject):
    """Client inputs for hmac-secret."""

    salt1: bytes
    salt2: bytes | None = None


@dataclass(eq=False, frozen=True)
class HMACGetSecretOutput(_JsonDataObject):
    """Client outputs for hmac-secret."""

    output1: bytes
    output2: bytes | None = None


def _prf_salt(secret):
    return sha256(b"WebAuthn PRF\0" + secret)


@dataclass(eq=False, frozen=True)
class AuthenticatorExtensionsPRFValues(_JsonDataObject):
    """Salt values for use with prf."""

    first: bytes
    second: bytes | None = None


@dataclass(eq=False, frozen=True)
class AuthenticatorExtensionsPRFInputs(_JsonDataObject):
    """Client inputs for prf."""

    eval: AuthenticatorExtensionsPRFValues | None = None
    eval_by_credential: Mapping[str, AuthenticatorExtensionsPRFValues] | None = None


@dataclass(eq=False, frozen=True)
class AuthenticatorExtensionsPRFOutputs(_JsonDataObject):
    """Client outputs for prf."""

    enabled: bool | None = None
    results: AuthenticatorExtensionsPRFValues | None = None


def _hmac_prepare_salts(allow_list, selected, prf, hmac):
    if prf:
        secrets = prf.eval
        by_creds = prf.eval_by_credential
        if by_creds:
            # Make sure all keys are valid IDs from allow_credentials
            if not allow_list:
                raise ValueError("evalByCredentials requires allowCredentials")
            ids = {websafe_encode(c.id) for c in allow_list}
            if not ids.issuperset(by_creds):
                raise ValueError("evalByCredentials contains invalid key")
            if selected:
                key = websafe_encode(selected.id)
                if key in by_creds:
                    secrets = by_creds[key]

        if not secrets:
            return

        salts = (
            _prf_salt(secrets.first),
            (_prf_salt(secrets.second) if secrets.second is not None else b""),
        )
    elif hmac:
        salts = hmac.salt1, hmac.salt2 or b""
    else:
        return

    if not (
        len(salts[0]) == HmacSecretExtension.SALT_LEN
        and (not salts[1] or len(salts[1]) == HmacSecretExtension.SALT_LEN)
    ):
        raise ValueError("Invalid salt length")

    return salts


def _hmac_format_outputs(enabled, decrypted, prf):
    output1 = decrypted[: HmacSecretExtension.SALT_LEN] if decrypted else None
    output2 = decrypted[HmacSecretExtension.SALT_LEN :] if decrypted else None

    if prf:
        result = AuthenticatorExtensionsPRFOutputs(
            enabled=enabled,
            results=(
                AuthenticatorExtensionsPRFValues(output1, output2) if output1 else None
            ),
        )
        # If result has no content, don't add an entry for it
        return {"prf": result} if result else None
    else:
        outputs = {}
        if enabled is not None:
            outputs["hmacCreateSecret"] = enabled
        if output1:
            outputs["hmacGetSecret"] = HMACGetSecretOutput(output1, output2)
        return outputs or None


class HmacSecretExtension(Ctap2Extension):
    """
    Implements the Pseudo-random function (prf) and the hmac-secret CTAP2 extensions.

    The hmac-secret extension is not directly available to clients by default, instead
    the prf extension is used.

    https://www.w3.org/TR/webauthn-3/#prf-extension

    https://fidoalliance.org/specs/fido-v2.1-rd-20201208/fido-client-to-authenticator-protocol-v2.1-rd-20201208.html#sctn-hmac-secret-extension

    :param allow_hmac_secret: Set to True to allow hmac-secret, in addition to prf.
    """

    NAME = "hmac-secret"
    MC_NAME = "hmac-secret-mc"
    SALT_LEN = 32

    def __init__(self, allow_hmac_secret=False):
        self._allow_hmac_secret = allow_hmac_secret

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions

    def make_credential(self, ctap, options, pin_protocol):
        c_inputs = options.extensions or {}
        prf = c_inputs.get("prf") is not None
        hmac = self._allow_hmac_secret and c_inputs.get("hmacCreateSecret") is True
        if pin_protocol and self.is_supported(ctap) and (prf or hmac):
            inputs: dict[str, Any] = {HmacSecretExtension.NAME: True}
            shared_secret = None
            if self.MC_NAME in ctap.info.extensions:
                prf_salts = AuthenticatorExtensionsPRFInputs.from_dict(
                    cast(Mapping | None, c_inputs.get("prf"))
                )
                hmac_salts = (
                    HMACGetSecretInput.from_dict(
                        cast(Mapping | None, c_inputs.get("hmacGetSecret"))
                    )
                    if hmac
                    else None
                )
                salts = _hmac_prepare_salts(None, None, prf_salts, hmac_salts)
                if salts:
                    client_pin = ClientPin(ctap, pin_protocol)
                    key_agreement, shared_secret = client_pin._get_shared_secret()
                    salt_enc = pin_protocol.encrypt(shared_secret, salts[0] + salts[1])
                    salt_auth = pin_protocol.authenticate(shared_secret, salt_enc)
                    inputs[HmacSecretExtension.MC_NAME] = {
                        1: key_agreement,
                        2: salt_enc,
                        3: salt_auth,
                        4: pin_protocol.VERSION,
                    }

            class Processor(RegistrationExtensionProcessor):
                def prepare_inputs(self, pin_token):
                    return inputs

                def prepare_outputs(self, response, pin_token):
                    extensions = response.auth_data.extensions or {}
                    enabled = extensions.get(HmacSecretExtension.NAME, False)
                    value = extensions.get(HmacSecretExtension.MC_NAME)
                    decrypted = (
                        pin_protocol.decrypt(shared_secret, value)
                        if value and shared_secret
                        else None
                    )
                    return _hmac_format_outputs(enabled, decrypted, prf)

            return Processor()

    def get_assertion(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        prf = AuthenticatorExtensionsPRFInputs.from_dict(
            cast(Mapping | None, inputs.get("prf"))
        )
        hmac = (
            HMACGetSecretInput.from_dict(
                cast(Mapping | None, inputs.get("hmacGetSecret"))
            )
            if self._allow_hmac_secret
            else None
        )

        if pin_protocol and self.is_supported(ctap) and (prf or hmac):
            client_pin = ClientPin(ctap, pin_protocol)
            key_agreement, shared_secret = client_pin._get_shared_secret()

            class Processing(AuthenticationExtensionProcessor):
                def prepare_inputs(self, selected, pin_token):
                    salts = _hmac_prepare_salts(
                        options.allow_credentials, selected, prf, hmac
                    )
                    if not salts:
                        return

                    salt_enc = pin_protocol.encrypt(shared_secret, salts[0] + salts[1])
                    salt_auth = pin_protocol.authenticate(shared_secret, salt_enc)

                    return {
                        HmacSecretExtension.NAME: {
                            1: key_agreement,
                            2: salt_enc,
                            3: salt_auth,
                            4: pin_protocol.VERSION,
                        }
                    }

                def prepare_outputs(self, response, pin_token):
                    extensions = response.auth_data.extensions or {}
                    value = extensions.get(HmacSecretExtension.NAME)
                    decrypted = (
                        pin_protocol.decrypt(shared_secret, value) if value else None
                    )
                    return _hmac_format_outputs(None, decrypted, prf)

            return Processing()


@dataclass(eq=False, frozen=True)
class AuthenticatorExtensionsLargeBlobInputs(_JsonDataObject):
    """Client inputs for largeBlob."""

    support: str | None = None
    read: bool | None = None
    write: bytes | None = None


@dataclass(eq=False, frozen=True)
class AuthenticatorExtensionsLargeBlobOutputs(_JsonDataObject):
    """Client outputs for largeBlob."""

    supported: bool | None = None
    blob: bytes | None = None
    written: bool | None = None


class LargeBlobExtension(Ctap2Extension):
    """
    Implements the Large Blob storage (largeBlob) WebAuthn extension.

    https://www.w3.org/TR/webauthn-3/#sctn-large-blob-extension
    """

    NAME = "largeBlobKey"

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions and ctap.info.options.get(
            "largeBlobs", False
        )

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        data = AuthenticatorExtensionsLargeBlobInputs.from_dict(
            cast(Mapping | None, inputs.get("largeBlob"))
        )
        if data:
            if data.read or data.write:
                raise ValueError("Invalid set of parameters")
            if data.support == "required" and not self.is_supported(ctap):
                raise ValueError("Authenticator does not support large blob storage")

            class Processor(RegistrationExtensionProcessor):
                def prepare_inputs(self, pin_token):
                    return {LargeBlobExtension.NAME: True}

                def prepare_outputs(self, response, pin_token):
                    return {
                        "largeBlob": AuthenticatorExtensionsLargeBlobOutputs(
                            supported=response.large_blob_key is not None
                        )
                    }

            return Processor()

    def get_assertion(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        data = AuthenticatorExtensionsLargeBlobInputs.from_dict(
            cast(Mapping | None, inputs.get("largeBlob"))
        )
        if data:
            if data.support or (data.read and data.write):
                raise ValueError("Invalid set of parameters")
            if not self.is_supported(ctap):
                raise ValueError("Authenticator does not support large blob storage")

            class Processor(AuthenticationExtensionProcessor):
                def prepare_outputs(self, response, pin_token):
                    assert data is not None  # noqa: S101 needed for mypy
                    blob_key = response.large_blob_key
                    if blob_key:
                        if data.read:
                            large_blobs = LargeBlobs(ctap)
                            blob = large_blobs.get_blob(blob_key)
                            return {
                                "largeBlob": AuthenticatorExtensionsLargeBlobOutputs(
                                    blob=blob
                                )
                            }
                        elif data.write:
                            large_blobs = LargeBlobs(ctap, pin_protocol, pin_token)
                            large_blobs.put_blob(blob_key, data.write)
                            return {
                                "largeBlob": AuthenticatorExtensionsLargeBlobOutputs(
                                    written=True
                                )
                            }

            return Processor(
                (
                    ClientPin.PERMISSION.LARGE_BLOB_WRITE
                    if data.write
                    else ClientPin.PERMISSION(0)
                ),
                inputs={LargeBlobExtension.NAME: True},
            )


class CredBlobExtension(Ctap2Extension):
    """
    Implements the Credential Blob (credBlob) CTAP2 extension.

    https://fidoalliance.org/specs/fido-v2.1-rd-20201208/fido-client-to-authenticator-protocol-v2.1-rd-20201208.html#sctn-credBlob-extension
    """

    NAME = "credBlob"

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        if self.is_supported(ctap):
            blob = inputs.get("credBlob")
            assert ctap.info.max_cred_blob_length is not None  # noqa: S101
            if blob and len(blob) <= ctap.info.max_cred_blob_length:
                return RegistrationExtensionProcessor(inputs={self.NAME: blob})

    def get_assertion(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        if self.is_supported(ctap) and inputs.get("getCredBlob") is True:
            return AuthenticationExtensionProcessor(inputs={self.NAME: True})


class CredProtectExtension(Ctap2Extension):
    """
    Implements the Credential Protection CTAP2 extension.

    https://fidoalliance.org/specs/fido-v2.1-rd-20201208/fido-client-to-authenticator-protocol-v2.1-rd-20201208.html#sctn-credProtect-extension
    """

    @unique
    class POLICY(Enum):
        OPTIONAL = "userVerificationOptional"
        OPTIONAL_WITH_LIST = "userVerificationOptionalWithCredentialIDList"
        REQUIRED = "userVerificationRequired"

        @classmethod
        def str2int(cls, policy: str) -> int:
            return list(cls).index(cls(policy)) + 1

    NAME = "credProtect"

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        policy = inputs.get("credentialProtectionPolicy")
        if policy:
            index = CredProtectExtension.POLICY.str2int(policy)
            enforce = inputs.get("enforceCredentialProtectionPolicy", False)
            if enforce and not self.is_supported(ctap) and index > 1:
                raise ValueError("Authenticator does not support Credential Protection")

            return RegistrationExtensionProcessor(inputs={self.NAME: index})


class MinPinLengthExtension(Ctap2Extension):
    """
    Implements the Minimum PIN Length (minPinLength) CTAP2 extension.

    https://fidoalliance.org/specs/fido-v2.1-rd-20201208/fido-client-to-authenticator-protocol-v2.1-rd-20201208.html#sctn-minpinlength-extension
    """

    NAME = "minPinLength"

    def is_supported(self, ctap):
        # NB: There is no key in the extensions field.
        return "setMinPINLength" in ctap.info.options

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        if self.is_supported(ctap) and inputs.get(self.NAME) is True:
            return RegistrationExtensionProcessor(inputs={self.NAME: True})


class PinComplexityPolicyExtension(Ctap2Extension):
    """
    Implements the PIN Complexity Policy (pinComplexityPolicy) CTAP2 extension.

    https://fidoalliance.org/specs/fido-v2.1-rd-20201208/fido-client-to-authenticator-protocol-v2.1-rd-20201208.html#sctn-minpinlength-extension
    """

    NAME = "pinComplexityPolicy"

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        if self.is_supported(ctap) and inputs.get(self.NAME) is True:
            return RegistrationExtensionProcessor(inputs={self.NAME: True})


@dataclass(eq=False, frozen=True)
class CredentialPropertiesOutput(_JsonDataObject):
    """Client outputs for credProps."""

    rk: bool | None = None


class CredPropsExtension(Ctap2Extension):
    """
    Implements the Credential Properties (credProps) WebAuthn extension.

    https://www.w3.org/TR/webauthn-3/#sctn-authenticator-credential-properties-extension
    """

    NAME = "credProps"

    def is_supported(self, ctap):
        # NB: There is no key in the extensions field.
        return True

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        if inputs.get(self.NAME) is True:
            selection = (
                options.authenticator_selection or AuthenticatorSelectionCriteria()
            )
            rk = selection.resident_key == ResidentKeyRequirement.REQUIRED or (
                selection.resident_key == ResidentKeyRequirement.PREFERRED
                and ctap.info.options.get("rk")
            )

            return RegistrationExtensionProcessor(
                outputs={self.NAME: CredentialPropertiesOutput(rk=rk)}
            )


@dataclass(eq=False, frozen=True)
class PaymentCurrencyAmount(_JsonDataObject):
    currency: str
    value: str


@dataclass(eq=False, frozen=True)
class PaymentCredentialInstrument(_JsonDataObject):
    display_name: str
    icon: str
    icon_must_be_shown: bool = True


@dataclass(eq=False, frozen=True)
class AuthenticationExtensionsPaymentInputs(_JsonDataObject):
    """Client inputs for payment."""

    is_payment: bool | None = None
    rp_id: str | None = None
    top_origin: str | None = None
    payee_name: str | None = None
    payee_origin: str | None = None
    total: PaymentCurrencyAmount | None = None
    instrument: PaymentCredentialInstrument | None = None


class ThirdPartyPaymentExtension(Ctap2Extension):
    """
    Implements the Third Party Payment (thirdPartyPayment) CTAP2.2 extension.

    https://fidoalliance.org/specs/fido-v2.2-ps-20250228/fido-client-to-authenticator-protocol-v2.2-ps-20250228.html#sctn-thirdPartyPayment-extension

    Note that most of the processing for the WebAuthn extension needs to be done by the
    client, see:
    https://www.w3.org/TR/secure-payment-confirmation/#sctn-collectedclientpaymentdata-dictionary

    As such, this extension is not included in the default extensions list, and should
    not be used without a client that supports the WebAuthn payment extension.
    """

    NAME = "thirdPartyPayment"

    def is_supported(self, ctap):
        return self.NAME in ctap.info.extensions

    def make_credential(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        data = AuthenticationExtensionsPaymentInputs.from_dict(
            cast(Mapping | None, inputs.get("payment"))
        )
        if self.is_supported(ctap) and data and data.is_payment:
            return RegistrationExtensionProcessor(inputs={self.NAME: True})

    def get_assertion(self, ctap, options, pin_protocol):
        inputs = options.extensions or {}
        data = AuthenticationExtensionsPaymentInputs.from_dict(
            cast(Mapping | None, inputs.get("payment"))
        )
        if self.is_supported(ctap) and data and data.is_payment:
            return AuthenticationExtensionProcessor(inputs={self.NAME: True})


_DEFAULT_EXTENSIONS = [
    HmacSecretExtension(),
    LargeBlobExtension(),
    CredBlobExtension(),
    CredProtectExtension(),
    MinPinLengthExtension(),
    CredPropsExtension(),
]
