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

import abc
import logging
from dataclasses import replace
from enum import IntEnum, unique
from threading import Event, Timer
from typing import Any, Callable, Mapping, Sequence, overload
from urllib.parse import urlparse

from ..cose import ES256
from ..ctap import CtapDevice, CtapError
from ..ctap1 import APDU, ApduError, Ctap1
from ..ctap2 import AssertionResponse, Ctap2, Info
from ..ctap2.extensions import (
    _DEFAULT_EXTENSIONS,
    AuthenticationExtensionProcessor,
    Ctap2Extension,
    RegistrationExtensionProcessor,
)
from ..ctap2.pin import ClientPin, PinProtocol
from ..hid import STATUS
from ..rpid import verify_rp_id
from ..utils import sha256
from ..webauthn import (
    Aaguid,
    AttestationConveyancePreference,
    AttestationObject,
    AuthenticationExtensionsClientOutputs,
    AuthenticationResponse,
    AuthenticatorAssertionResponse,
    AuthenticatorAttachment,
    AuthenticatorAttestationResponse,
    AuthenticatorSelectionCriteria,
    CollectedClientData,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRequestOptions,
    PublicKeyCredentialType,
    RegistrationResponse,
    ResidentKeyRequirement,
    UserVerificationRequirement,
    _as_cbor,
)

logger = logging.getLogger(__name__)


class ClientError(Exception):
    """Base error raised by clients."""

    @unique
    class ERR(IntEnum):
        """Error codes for ClientError."""

        OTHER_ERROR = 1
        BAD_REQUEST = 2
        CONFIGURATION_UNSUPPORTED = 3
        DEVICE_INELIGIBLE = 4
        TIMEOUT = 5

        def __call__(self, cause=None):
            return ClientError(self, cause)

    def __init__(self, code, cause=None):
        self.code = ClientError.ERR(code)
        self.cause = cause

    def __repr__(self):
        r = "Client error: {0} - {0.name}".format(self.code)
        if self.cause:
            r += f" (cause: {self.cause})"
        return r


def _ctap2client_err(e, err_cls=ClientError):
    if e.code in [CtapError.ERR.CREDENTIAL_EXCLUDED, CtapError.ERR.NO_CREDENTIALS]:
        ce = ClientError.ERR.DEVICE_INELIGIBLE
    elif e.code in [
        CtapError.ERR.KEEPALIVE_CANCEL,
        CtapError.ERR.ACTION_TIMEOUT,
        CtapError.ERR.USER_ACTION_TIMEOUT,
    ]:
        ce = ClientError.ERR.TIMEOUT
    elif e.code in [
        CtapError.ERR.UNSUPPORTED_ALGORITHM,
        CtapError.ERR.UNSUPPORTED_OPTION,
        CtapError.ERR.KEY_STORE_FULL,
    ]:
        ce = ClientError.ERR.CONFIGURATION_UNSUPPORTED
    elif e.code in [
        CtapError.ERR.INVALID_COMMAND,
        CtapError.ERR.CBOR_UNEXPECTED_TYPE,
        CtapError.ERR.INVALID_CBOR,
        CtapError.ERR.MISSING_PARAMETER,
        CtapError.ERR.INVALID_OPTION,
        CtapError.ERR.PUAT_REQUIRED,
        CtapError.ERR.PIN_INVALID,
        CtapError.ERR.PIN_BLOCKED,
        CtapError.ERR.PIN_NOT_SET,
        CtapError.ERR.PIN_POLICY_VIOLATION,
        CtapError.ERR.PIN_TOKEN_EXPIRED,
        CtapError.ERR.PIN_AUTH_INVALID,
        CtapError.ERR.PIN_AUTH_BLOCKED,
        CtapError.ERR.REQUEST_TOO_LARGE,
        CtapError.ERR.OPERATION_DENIED,
    ]:
        ce = ClientError.ERR.BAD_REQUEST
    else:
        ce = ClientError.ERR.OTHER_ERROR

    return err_cls(ce, e)


class PinRequiredError(ClientError):
    """Raised when a call cannot be completed without providing PIN."""

    def __init__(
        self, code=ClientError.ERR.BAD_REQUEST, cause="PIN required but not provided"
    ):
        super().__init__(code, cause)


def _call_polling(poll_delay, event, on_keepalive, func, *args, **kwargs):
    event = event or Event()
    while not event.is_set():
        try:
            return func(*args, **kwargs)
        except ApduError as e:
            if e.code == APDU.USE_NOT_SATISFIED:
                if on_keepalive:
                    on_keepalive(STATUS.UPNEEDED)
                    on_keepalive = None
                event.wait(poll_delay)
            else:
                raise ClientError.ERR.OTHER_ERROR(e)
        except CtapError as e:
            raise _ctap2client_err(e)
    raise ClientError.ERR.TIMEOUT()


class AssertionSelection:
    """GetAssertion result holding one or more assertions.

    Since multiple assertions may be retured by Fido2Client.get_assertion, this result
    is returned which can be used to select a specific response to get.
    """

    def __init__(
        self,
        client_data: CollectedClientData,
        assertions: Sequence[AssertionResponse],
        extension_results: Mapping[str, Any] = {},
    ):
        self._client_data = client_data
        self._assertions = assertions
        self._extension_results = extension_results

    def get_assertions(self) -> Sequence[AssertionResponse]:
        """Get the raw AssertionResponses available to inspect before selecting one."""
        return self._assertions

    def _get_extension_results(self, assertion: AssertionResponse) -> Mapping[str, Any]:
        return self._extension_results

    def get_response(self, index: int) -> AuthenticationResponse:
        """Get a single response."""
        assertion = self._assertions[index]

        return AuthenticationResponse(
            raw_id=assertion.credential["id"],
            response=AuthenticatorAssertionResponse(
                client_data=self._client_data,
                authenticator_data=assertion.auth_data,
                signature=assertion.signature,
                user_handle=assertion.user["id"] if assertion.user else None,
            ),
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
            client_extension_results=AuthenticationExtensionsClientOutputs(
                self._get_extension_results(assertion)
            ),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )


class WebAuthnClient(abc.ABC):
    """Base class for a WebAuthn client, supporting registration and authentication."""

    @abc.abstractmethod
    def make_credential(
        self,
        options: PublicKeyCredentialCreationOptions,
        event: Event | None = None,
    ) -> RegistrationResponse:
        """Creates a credential.

        :param options: PublicKeyCredentialCreationOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_assertion(
        self,
        options: PublicKeyCredentialRequestOptions,
        event: Event | None = None,
    ) -> AssertionSelection:
        """Get an assertion.

        :param options: PublicKeyCredentialRequestOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """
        raise NotImplementedError()


class UserInteraction:
    """Provides user interaction to the Client.

    Users of Fido2Client should subclass this to implement asking the user to perform
    specific actions, such as entering a PIN or touching their"""

    def prompt_up(self) -> None:
        """Called when the authenticator is awaiting a user presence check."""
        logger.info("User Presence check required.")

    def request_pin(
        self, permissions: ClientPin.PERMISSION, rp_id: str | None
    ) -> str | None:
        """Called when the client requires a PIN from the user.

        Should return a PIN, or None/Empty to cancel."""
        logger.info("PIN requested, but UserInteraction does not support it.")
        return None

    def request_uv(self, permissions: ClientPin.PERMISSION, rp_id: str | None) -> bool:
        """Called when the client is about to request UV from the user.

        Should return True if allowed, or False to cancel."""
        logger.info("User Verification requested.")
        return True


class ClientDataCollector(abc.ABC):
    """Provides client data and logic to the Client.

    Users should subclass this to implement custom behavior for determining the origin,
    validating the RP ID, and providing client data for a request.
    """

    @abc.abstractmethod
    def collect_client_data(
        self,
        options: PublicKeyCredentialCreationOptions | PublicKeyCredentialRequestOptions,
    ) -> tuple[CollectedClientData, str]:
        """Called when the client is preparing a request.

        Should return a CollectedClientData object with the client data for the request,
        as well as the RP ID of the credential.
        """


class DefaultClientDataCollector(ClientDataCollector):
    """Default implementation of ClientDataProvider.

    This implementation uses a fixed origin, it can be subclassed to customize specific
    behavior.
    """

    def __init__(self, origin: str, verify: Callable[[str, str], bool] = verify_rp_id):
        self._origin = origin
        self._verify = verify

    def get_rp_id(
        self,
        options: PublicKeyCredentialCreationOptions | PublicKeyCredentialRequestOptions,
        origin: str,
    ) -> str:
        """Get the RP ID for the given options and origin."""
        if isinstance(options, PublicKeyCredentialCreationOptions):
            rp_id = options.rp.id
        elif isinstance(options, PublicKeyCredentialRequestOptions):
            rp_id = options.rp_id
        else:
            raise ValueError("Invalid options type.")

        if rp_id is None:
            url = urlparse(origin)
            if url.scheme != "https" or not url.netloc:
                raise ClientError.ERR.BAD_REQUEST(
                    "RP ID required for non-https origin."
                )
            return url.netloc
        else:
            return rp_id

    def verify_rp_id(self, rp_id: str, origin: str) -> None:
        """Verify the RP ID for the given origin."""
        try:
            if self._verify(rp_id, origin):
                return
        except Exception:  # noqa: S110
            pass  # Fall through to ClientError
        raise ClientError.ERR.BAD_REQUEST()

    def get_request_type(self, options) -> str:
        """Get the request type for the given options."""
        if isinstance(options, PublicKeyCredentialCreationOptions):
            return CollectedClientData.TYPE.CREATE
        elif isinstance(options, PublicKeyCredentialRequestOptions):
            return CollectedClientData.TYPE.GET
        else:
            raise ValueError("Invalid options type.")

    def collect_client_data(self, options):
        # Get the effective RP ID from the request options, falling back to the origin
        rp_id = self.get_rp_id(options, self._origin)
        # Validate that the RP ID is valid for the given origin
        self.verify_rp_id(rp_id, self._origin)

        # Construct the client data
        return (
            CollectedClientData.create(
                type=self.get_request_type(options),
                origin=self._origin,
                challenge=options.challenge,
            ),
            rp_id,
        )


def _user_keepalive(user_interaction):
    def on_keepalive(status):
        if status == STATUS.UPNEEDED:  # Waiting for touch
            user_interaction.prompt_up()

    return on_keepalive


class _ClientBackend(abc.ABC):
    info: Info

    @abc.abstractmethod
    def selection(self, event: Event | None) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    def do_make_credential(
        self,
        options: PublicKeyCredentialCreationOptions,
        client_data: CollectedClientData,
        rp_id: str,
        enterprise_rpid_list: Sequence[str] | None,
        event: Event,
    ) -> RegistrationResponse:
        raise NotImplementedError()

    @abc.abstractmethod
    def do_get_assertion(
        self,
        options: PublicKeyCredentialRequestOptions,
        client_data: CollectedClientData,
        rp_id: str,
        event: Event,
    ) -> AssertionSelection:
        raise NotImplementedError()


class _Ctap1ClientBackend(_ClientBackend):
    def __init__(self, device: CtapDevice, user_interaction: UserInteraction):
        self.ctap1 = Ctap1(device)
        self.info = Info(versions=["U2F_V2"], extensions=[], aaguid=Aaguid.NONE)
        self._poll_delay = 0.25
        self._on_keepalive = _user_keepalive(user_interaction)

    def selection(self, event):
        _call_polling(
            self._poll_delay,
            event,
            None,
            self.ctap1.register,
            b"\0" * 32,
            b"\0" * 32,
        )

    def do_make_credential(
        self,
        options,
        client_data,
        rp_id,
        enterprise_rpid_list,
        event,
    ):
        key_params = options.pub_key_cred_params
        exclude_list = options.exclude_credentials
        selection = options.authenticator_selection or AuthenticatorSelectionCriteria()
        rk = selection.require_resident_key
        user_verification = selection.user_verification

        if (
            rk
            or user_verification == UserVerificationRequirement.REQUIRED
            or ES256.ALGORITHM not in [p.alg for p in key_params]
            or options.attestation == AttestationConveyancePreference.ENTERPRISE
        ):
            raise CtapError(CtapError.ERR.UNSUPPORTED_OPTION)

        app_param = sha256(rp_id.encode())

        dummy_param = b"\0" * 32
        for cred in exclude_list or []:
            key_handle = cred.id
            try:
                self.ctap1.authenticate(dummy_param, app_param, key_handle, True)
                raise ClientError.ERR.OTHER_ERROR()  # Shouldn't happen
            except ApduError as e:
                if e.code == APDU.USE_NOT_SATISFIED:
                    _call_polling(
                        self._poll_delay,
                        event,
                        self._on_keepalive,
                        self.ctap1.register,
                        dummy_param,
                        dummy_param,
                    )
                    raise ClientError.ERR.DEVICE_INELIGIBLE()

        att_obj = AttestationObject.from_ctap1(
            app_param,
            _call_polling(
                self._poll_delay,
                event,
                self._on_keepalive,
                self.ctap1.register,
                client_data.hash,
                app_param,
            ),
        )
        credential = att_obj.auth_data.credential_data
        assert credential is not None  # noqa: S101

        return RegistrationResponse(
            raw_id=credential.credential_id,
            response=AuthenticatorAttestationResponse(
                client_data=client_data, attestation_object=att_obj
            ),
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
            client_extension_results=AuthenticationExtensionsClientOutputs({}),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )

    def do_get_assertion(
        self,
        options,
        client_data,
        rp_id,
        event,
    ):
        allow_list = options.allow_credentials
        user_verification = options.user_verification

        if user_verification == UserVerificationRequirement.REQUIRED or not allow_list:
            raise CtapError(CtapError.ERR.UNSUPPORTED_OPTION)

        app_param = sha256(rp_id.encode())
        client_param = client_data.hash
        for cred in allow_list:
            try:
                auth_resp = _call_polling(
                    self._poll_delay,
                    event,
                    self._on_keepalive,
                    self.ctap1.authenticate,
                    client_param,
                    app_param,
                    cred.id,
                )
                assertions = [
                    AssertionResponse.from_ctap1(app_param, _as_cbor(cred), auth_resp)
                ]
                return AssertionSelection(client_data, assertions)
            except ClientError as e:
                if e.code == ClientError.ERR.TIMEOUT:
                    raise  # Other errors are ignored so we move to the next.
        raise ClientError.ERR.DEVICE_INELIGIBLE()


class _Ctap2ClientAssertionSelection(AssertionSelection):
    def __init__(
        self,
        client_data: CollectedClientData,
        assertions: Sequence[AssertionResponse],
        extensions: Sequence[AuthenticationExtensionProcessor],
        pin_token: bytes | None,
    ):
        super().__init__(client_data, assertions)
        self._extensions = extensions
        self._pin_token = pin_token

    def _get_extension_results(self, assertion):
        # Process extension outputs
        extension_outputs = {}
        try:
            for ext in self._extensions:
                output = ext.prepare_outputs(assertion, self._pin_token)
                if output:
                    extension_outputs.update(output)
        except ValueError as e:
            raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(e)
        return extension_outputs


@overload
def _cbor_list(values: Sequence) -> list: ...


@overload
def _cbor_list(values: None) -> None: ...


def _cbor_list(values):
    if not values:
        return None
    return [_as_cbor(v) for v in values]


class _Ctap2ClientBackend(_ClientBackend):
    def __init__(
        self,
        device: CtapDevice,
        user_interaction: UserInteraction,
        extensions: Sequence[Ctap2Extension],
    ):
        self.ctap2 = Ctap2(device)
        self.info = self.ctap2.info
        self._extensions = extensions
        self.user_interaction = user_interaction

    def _filter_creds(
        self, rp_id, cred_list, pin_protocol, pin_token, event, on_keepalive
    ):
        # Use fresh info
        info = self.ctap2.get_info()

        # Filter out credential IDs which are too long
        max_len = info.max_cred_id_length
        if max_len:
            cred_list = [c for c in cred_list if len(c.id) <= max_len]

        client_data_hash = b"\0" * 32
        if pin_token:
            pin_auth = pin_protocol.authenticate(pin_token, client_data_hash)
            version = pin_protocol.VERSION
        else:
            pin_auth = None
            version = None

        max_creds = info.max_creds_in_list or 1
        while cred_list:
            chunk = cred_list[:max_creds]
            try:
                assertions = self.ctap2.get_assertions(
                    rp_id,
                    client_data_hash,
                    _cbor_list(chunk),
                    None,
                    {"up": False},
                    pin_auth,
                    version,
                    event=event,
                    on_keepalive=on_keepalive,
                )
                if len(chunk) == 1:
                    # Credential ID might be omitted from assertions
                    return chunk[0]
                else:
                    return PublicKeyCredentialDescriptor(**assertions[0].credential)
            except CtapError as e:
                match e.code:
                    case CtapError.ERR.REQUEST_TOO_LARGE if max_creds > 1:
                        # Message is too large, try smaller chunks
                        max_creds -= 1
                    case CtapError.ERR.NO_CREDENTIALS:
                        # All creds in chunk are discarded
                        cred_list = cred_list[max_creds:]
                    case _:
                        raise

        # No matches found
        return None

    def selection(self, event):
        if "FIDO_2_1" in self.ctap2.info.versions:
            self.ctap2.selection(event=event)
        else:
            # Selection not supported, make dummy credential instead
            try:
                self.ctap2.make_credential(
                    b"\0" * 32,
                    {"id": "example.com", "name": "example.com"},
                    {"id": b"dummy", "name": "dummy"},
                    [{"type": "public-key", "alg": -7}],
                    pin_uv_param=b"",
                    event=event,
                )
            except CtapError as e:
                if e.code in (
                    CtapError.ERR.PIN_NOT_SET,
                    CtapError.ERR.PIN_INVALID,
                    CtapError.ERR.PIN_AUTH_INVALID,
                ):
                    return
                raise

    def _should_use_uv(self, info, user_verification, permissions):
        uv_supported = any(k in info.options for k in ("uv", "clientPin", "bioEnroll"))
        uv_configured = any(
            info.options.get(k) for k in ("uv", "clientPin", "bioEnroll")
        )
        mc = ClientPin.PERMISSION.MAKE_CREDENTIAL & permissions != 0
        additional_perms = permissions & ~(
            ClientPin.PERMISSION.MAKE_CREDENTIAL | ClientPin.PERMISSION.GET_ASSERTION
        )

        if (
            user_verification == UserVerificationRequirement.REQUIRED
            or (
                user_verification in (UserVerificationRequirement.PREFERRED, None)
                and uv_supported
            )
            or info.options.get("alwaysUv")
        ):
            if not uv_configured:
                raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(
                    "User verification not configured/supported"
                )
            return True
        elif mc and uv_configured and not info.options.get("makeCredUvNotRqd"):
            return True
        elif uv_configured and additional_perms:
            return True
        return False

    def _get_token(
        self,
        info,
        client_pin,
        permissions,
        rp_id,
        event,
        on_keepalive,
        allow_internal_uv,
        allow_uv,
    ):
        # Prefer UV
        if allow_uv and info.options.get("uv"):
            if ClientPin.is_token_supported(info):
                if self.user_interaction.request_uv(permissions, rp_id):
                    return client_pin.get_uv_token(
                        permissions, rp_id, event, on_keepalive
                    )
            elif allow_internal_uv:
                if self.user_interaction.request_uv(permissions, rp_id):
                    return None  # No token, use uv=True

        # PIN if UV not supported/allowed.
        if info.options.get("clientPin"):
            pin = self.user_interaction.request_pin(permissions, rp_id)
            if pin:
                return client_pin.get_pin_token(pin, permissions, rp_id)
            raise PinRequiredError()

        # Client PIN not configured.
        raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(
            "User verification not configured"
        )

    def _get_auth_params(
        self,
        pin_protocol,
        rp_id,
        user_verification,
        permissions,
        allow_uv,
        event,
        on_keepalive,
    ):
        info = self.ctap2.get_info()

        pin_token = None
        internal_uv = False
        if self._should_use_uv(info, user_verification, permissions):
            client_pin = ClientPin(self.ctap2, pin_protocol)
            allow_internal_uv = (
                permissions
                & ~(
                    ClientPin.PERMISSION.MAKE_CREDENTIAL
                    | ClientPin.PERMISSION.GET_ASSERTION
                )
                == 0
            )
            pin_token = self._get_token(
                info,
                client_pin,
                permissions,
                rp_id,
                event,
                on_keepalive,
                allow_internal_uv,
                allow_uv,
            )
            if not pin_token:
                internal_uv = True
        return pin_token, internal_uv

    def do_make_credential(
        self,
        options,
        client_data,
        rp_id,
        enterprise_rpid_list,
        event,
    ):
        user = options.user
        key_params = options.pub_key_cred_params
        exclude_list = options.exclude_credentials
        selection = options.authenticator_selection or AuthenticatorSelectionCriteria()
        user_verification = selection.user_verification

        on_keepalive = _user_keepalive(self.user_interaction)
        info = self.ctap2.get_info()

        # Handle enterprise attestation
        enterprise_attestation = None
        if options.attestation == AttestationConveyancePreference.ENTERPRISE:
            if info.options.get("ep"):
                if enterprise_rpid_list is not None:
                    # Platform facilitated
                    if rp_id in enterprise_rpid_list:
                        enterprise_attestation = 2
                else:
                    # Vendor facilitated
                    enterprise_attestation = 1

        # Negotiate PIN/UV protocol version
        for proto in ClientPin.PROTOCOLS:
            if proto.VERSION in info.pin_uv_protocols:
                pin_protocol: PinProtocol | None = proto()
                break
        else:
            pin_protocol = None

        used_extensions: list[RegistrationExtensionProcessor] = []
        allow_uv = True

        def _do_make():
            # Gather UV permissions
            permissions = ClientPin.PERMISSION.MAKE_CREDENTIAL
            if exclude_list:
                # We need this for filtering the exclude_list
                permissions |= ClientPin.PERMISSION.GET_ASSERTION

            # Initialize extensions and add extension permissions
            used_extensions.clear()
            for e in self._extensions:
                ext = e.make_credential(self.ctap2, options, pin_protocol)
                if ext:
                    used_extensions.append(ext)
                    permissions |= ext.permissions

            # Handle auth
            pin_token, internal_uv = self._get_auth_params(
                pin_protocol,
                rp_id,
                user_verification,
                permissions,
                allow_uv,
                event,
                on_keepalive,
            )

            if exclude_list:
                exclude_cred = self._filter_creds(
                    rp_id, exclude_list, pin_protocol, pin_token, event, on_keepalive
                )
                # We know the request will fail if exclude_cred is not None here
                # BUT DO NOT FAIL EARLY! We still need to prompt for UP, so we keep
                # processing the request
            else:
                exclude_cred = None

            # Process extensions
            extension_inputs = {}
            try:
                for ext in used_extensions:
                    auth_input = ext.prepare_inputs(pin_token)
                    if auth_input:
                        extension_inputs.update(auth_input)
            except ValueError as e:
                raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(e)

            can_rk = info.options.get("rk")
            rk = selection.resident_key == ResidentKeyRequirement.REQUIRED or (
                selection.resident_key == ResidentKeyRequirement.PREFERRED and can_rk
            )

            if not (rk or internal_uv):
                opts = None
            else:
                opts = {}
                if rk:
                    if not can_rk:
                        raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(
                            "Resident key not supported"
                        )
                    opts["rk"] = True
                if internal_uv:
                    opts["uv"] = True

            # Calculate pin_auth
            client_data_hash = client_data.hash
            if pin_protocol and pin_token:
                pin_auth: tuple[bytes | None, int | None] = (
                    pin_protocol.authenticate(pin_token, client_data_hash),
                    pin_protocol.VERSION,
                )
            else:
                pin_auth = (None, None)

            # Perform make credential
            return (
                self.ctap2.make_credential(
                    client_data_hash,
                    _as_cbor(replace(options.rp, id=rp_id)),
                    _as_cbor(user),
                    _cbor_list(key_params),
                    [_as_cbor(exclude_cred)] if exclude_cred else None,
                    extension_inputs or None,
                    opts,
                    *pin_auth,
                    enterprise_attestation,
                    event=event,
                    on_keepalive=on_keepalive,
                ),
                pin_token,
            )

        dev = self.ctap2.device
        reconnected = False
        while True:
            try:
                att_resp, pin_token = _do_make()
                break
            except CtapError as e:
                # The Authenticator may still require UV, try again
                if (
                    e.code == CtapError.ERR.PUAT_REQUIRED
                    and user_verification == UserVerificationRequirement.DISCOURAGED
                ):
                    user_verification = UserVerificationRequirement.REQUIRED
                    continue
                # UV may be blocked, try again (once) with PIN
                if e.code == CtapError.ERR.UV_BLOCKED and allow_uv:
                    allow_uv = False
                    continue
                # NFC may require reconnect
                connect = getattr(dev, "connect", None)
                if (
                    e.code == CtapError.ERR.PIN_AUTH_BLOCKED
                    and connect
                    and not reconnected
                ):
                    dev.close()
                    connect()
                    reconnected = True  # We only want to try this once
                    continue
                raise

        # Process extension outputs
        extension_outputs = {}
        try:
            for ext in used_extensions:
                output = ext.prepare_outputs(att_resp, pin_token)
                if output is not None:
                    extension_outputs.update(output)
        except ValueError as e:
            raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(e)

        att_obj = AttestationObject.create(
            att_resp.fmt, att_resp.auth_data, att_resp.att_stmt
        )

        credential = att_obj.auth_data.credential_data
        assert credential is not None  # noqa: S101

        return RegistrationResponse(
            raw_id=credential.credential_id,
            response=AuthenticatorAttestationResponse(
                client_data=client_data, attestation_object=att_obj
            ),
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
            client_extension_results=AuthenticationExtensionsClientOutputs(
                extension_outputs
            ),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )

    def do_get_assertion(
        self,
        options,
        client_data,
        rp_id,
        event,
    ):
        rp_id = options.rp_id
        allow_list = options.allow_credentials
        user_verification = options.user_verification

        on_keepalive = _user_keepalive(self.user_interaction)

        # Negotiate PIN/UV protocol version
        for proto in ClientPin.PROTOCOLS:
            if proto.VERSION in self.info.pin_uv_protocols:
                pin_protocol: PinProtocol | None = proto()
                break
        else:
            pin_protocol = None

        allow_uv = True

        def _do_auth():
            # Gather UV permissions
            permissions = ClientPin.PERMISSION.GET_ASSERTION

            # Initialize extensions and add extension permissions
            used_extensions = []
            for e in self._extensions:
                ext = e.get_assertion(self.ctap2, options, pin_protocol)
                if ext:
                    used_extensions.append(ext)
                    permissions |= ext.permissions

            # Handle auth
            pin_token, internal_uv = self._get_auth_params(
                pin_protocol,
                rp_id,
                user_verification,
                permissions,
                allow_uv,
                event,
                on_keepalive,
            )

            if allow_list:
                selected_cred = self._filter_creds(
                    rp_id, allow_list, pin_protocol, pin_token, event, on_keepalive
                )
                # We know the request will fail if selected_cred is None here
                # BUT DO NOT FAIL EARLY! We still need to prompt for UP, so we keep
                # processing the request
            else:
                selected_cred = None

            # Process extensions
            extension_inputs = {}
            try:
                for ext in used_extensions:
                    inputs = ext.prepare_inputs(selected_cred, pin_token)
                    if inputs:
                        extension_inputs.update(inputs)
            except ValueError as e:
                raise ClientError.ERR.CONFIGURATION_UNSUPPORTED(e)

            opts = {"uv": True} if internal_uv else None

            # Calculate pin_auth
            client_data_hash = client_data.hash
            if pin_protocol and pin_token:
                pin_auth: tuple[bytes | None, int | None] = (
                    pin_protocol.authenticate(pin_token, client_data_hash),
                    pin_protocol.VERSION,
                )
            else:
                pin_auth = (None, None)

            if allow_list and not selected_cred:
                # We still need to send a dummy value if there was an allow_list
                # but no matches were found:
                selected_cred = PublicKeyCredentialDescriptor(
                    type=allow_list[0].type, id=b"\0"
                )

            # Perform get assertion
            assertions = self.ctap2.get_assertions(
                rp_id,
                client_data_hash,
                [_as_cbor(selected_cred)] if selected_cred else None,
                extension_inputs or None,
                opts,
                *pin_auth,
                event=event,
                on_keepalive=on_keepalive,
            )

            return _Ctap2ClientAssertionSelection(
                client_data, assertions, used_extensions, pin_token
            )

        dev = self.ctap2.device
        reconnected = False
        while True:
            try:
                return _do_auth()
            except CtapError as e:
                # The Authenticator may still require UV, try again
                if (
                    e.code == CtapError.ERR.PUAT_REQUIRED
                    and user_verification == UserVerificationRequirement.DISCOURAGED
                ):
                    user_verification = UserVerificationRequirement.REQUIRED
                    continue
                # UV may be blocked, try again (once) with PIN
                if e.code == CtapError.ERR.UV_BLOCKED and allow_uv:
                    allow_uv = False
                    continue
                # NFC may require reconnect
                connect = getattr(dev, "connect", None)
                if (
                    e.code == CtapError.ERR.PIN_AUTH_BLOCKED
                    and connect
                    and not reconnected
                ):
                    dev.close()
                    connect()
                    reconnected = True  # We only want to try this once
                    continue
                raise


class Fido2Client(WebAuthnClient):
    """WebAuthn-like client implementation.

    The client allows registration and authentication of WebAuthn credentials against
    an Authenticator using CTAP (1 or 2).

    :param device: CtapDevice to use.
    :param str origin: The origin to use.
    :param verify: Function to verify an RP ID for a given origin.
    """

    def __init__(
        self,
        device: CtapDevice,
        client_data_collector: ClientDataCollector,
        user_interaction: UserInteraction = UserInteraction(),
        extensions: Sequence[Ctap2Extension] = _DEFAULT_EXTENSIONS,
    ):
        self._client_data_collector = client_data_collector

        # TODO: Decide how to configure this list.
        self._enterprise_rpid_list: Sequence[str] | None = None

        try:
            self._backend: _ClientBackend = _Ctap2ClientBackend(
                device, user_interaction, extensions
            )
        except (ValueError, CtapError):
            self._backend = _Ctap1ClientBackend(device, user_interaction)

    @property
    def info(self) -> Info:
        return self._backend.info

    def selection(self, event: Event | None = None) -> None:
        try:
            self._backend.selection(event)
        except CtapError as e:
            raise _ctap2client_err(e)

    def make_credential(
        self,
        options: PublicKeyCredentialCreationOptions,
        event: Event | None = None,
    ) -> RegistrationResponse:
        """Creates a credential.

        :param options: PublicKeyCredentialCreationOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """

        options = PublicKeyCredentialCreationOptions.from_dict(options)
        event = event or Event()
        if options.timeout:
            timer = Timer(options.timeout / 1000, event.set)
            timer.daemon = True
            timer.start()
        else:
            timer = None

        # Gather client data, RP ID from client
        client_data, rp_id = self._client_data_collector.collect_client_data(options)
        logger.debug(f"Register a new credential for RP ID: {rp_id}")

        try:
            return self._backend.do_make_credential(
                options,
                client_data,
                rp_id,
                self._enterprise_rpid_list,
                event,
            )
        except CtapError as e:
            raise _ctap2client_err(e)
        finally:
            if timer:
                timer.cancel()

    def get_assertion(
        self,
        options: PublicKeyCredentialRequestOptions,
        event: Event | None = None,
    ) -> AssertionSelection:
        """Get an assertion.

        :param options: PublicKeyCredentialRequestOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """

        options = PublicKeyCredentialRequestOptions.from_dict(options)
        event = event or Event()
        if options.timeout:
            timer = Timer(options.timeout / 1000, event.set)
            timer.daemon = True
            timer.start()
        else:
            timer = None

        # Gather client data, RP ID from client
        client_data, rp_id = self._client_data_collector.collect_client_data(options)
        logger.debug(f"Assert a credential for RP ID: {rp_id}")

        try:
            return self._backend.do_get_assertion(
                options,
                client_data,
                rp_id,
                event,
            )
        except CtapError as e:
            raise _ctap2client_err(e)
        finally:
            if timer:
                timer.cancel()
