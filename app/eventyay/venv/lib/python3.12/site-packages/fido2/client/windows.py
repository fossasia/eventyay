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

import ctypes
import logging
from threading import Thread
from typing import Any, Mapping, Sequence, cast

from ..ctap2 import AssertionResponse
from ..ctap2.extensions import (
    AuthenticatorExtensionsLargeBlobInputs,
    AuthenticatorExtensionsLargeBlobOutputs,
    AuthenticatorExtensionsPRFInputs,
    AuthenticatorExtensionsPRFOutputs,
    CredentialPropertiesOutput,
    CredProtectExtension,
    HMACGetSecretInput,
    HMACGetSecretOutput,
)
from ..utils import _JsonDataObject, websafe_decode
from ..webauthn import (
    AttestationConveyancePreference,
    AttestationObject,
    AuthenticationExtensionsClientOutputs,
    AuthenticatorAttachment,
    AuthenticatorAttestationResponse,
    AuthenticatorData,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialRequestOptions,
    PublicKeyCredentialType,
    RegistrationResponse,
    ResidentKeyRequirement,
    _as_cbor,
)
from . import (
    AssertionSelection,
    ClientDataCollector,
    ClientError,
    WebAuthnClient,
    _cbor_list,
)
from .win_api import (
    BOOL,
    GUID,
    WEBAUTHN,
    WEBAUTHN_API_VERSION,
    WebAuthNAssertion,
    WebAuthNAttestationConveyancePreference,
    WebAuthNAuthenticatorAttachment,
    WebAuthNClientData,
    WebAuthNCoseCredentialParameters,
    WebAuthNCredBlobExtension,
    WebAuthNCredentialAttestation,
    WebAuthNCredProtectExtensionIn,
    WebAuthNCredWithHmacSecretSalt,
    WebAuthNEnterpriseAttestation,
    WebAuthNExtension,
    WebAuthNGetAssertionOptions,
    WebAuthNHmacSecretSalt,
    WebAuthNHmacSecretSaltValues,
    WebAuthNLargeBlobOperation,
    WebAuthNLargeBlobSupport,
    WebAuthNMakeCredentialOptions,
    WebAuthNRpEntityInformation,
    WebAuthNUserEntityInformation,
    WebAuthNUserVerification,
    WebAuthNUserVerificationRequirement,
    windll,
)

logger = logging.getLogger(__name__)

_extension_output_types: dict[str, type[_JsonDataObject]] = {
    "hmacGetSecret": HMACGetSecretOutput,
    "prf": AuthenticatorExtensionsPRFOutputs,
    "largeBlob": AuthenticatorExtensionsLargeBlobOutputs,
    "credProps": CredentialPropertiesOutput,
}


def _wrap_ext(key, value):
    if key in _extension_output_types:
        return _extension_output_types[key].from_dict(value)
    return value


class CancelThread(Thread):
    def __init__(self, event):
        super().__init__()
        self.daemon = True
        self._completed = False
        self.event = event
        self.guid = GUID()
        WEBAUTHN.WebAuthNGetCancellationId(ctypes.byref(self.guid))

    def run(self):
        self.event.wait()
        if not self._completed:
            WEBAUTHN.WebAuthNCancelCurrentOperation(ctypes.byref(self.guid))

    def complete(self):
        self._completed = True
        self.event.set()
        self.join()


class WindowsClient(WebAuthnClient):
    """Fido2Client-like class using the Windows WebAuthn API.

    Note: This class only works on Windows 10 19H1 or later. This is also when Windows
    started restricting access to FIDO devices, causing the standard client classes to
    require admin priveleges to run (unlike this one).

    :param str origin: The origin to use.
    :param verify: Function to verify an RP ID for a given origin.
    :param ctypes.wintypes.HWND handle: (optional) Window reference to use.
    """

    def __init__(
        self,
        client_data_collector: ClientDataCollector,
        handle=None,
        allow_hmac_secret=False,
    ):
        self.handle = handle or windll.user32.GetForegroundWindow()
        self._client_data_collector = client_data_collector

        self._allow_hmac_secret = allow_hmac_secret

        # TODO: Decide how to configure this list.
        self._enterprise_rpid_list: Sequence[str] | None = None

    @staticmethod
    def is_available() -> bool:
        return WEBAUTHN_API_VERSION > 0

    def make_credential(self, options, event=None):
        """Create a credential using Windows WebAuthN APIs.

        :param options: PublicKeyCredentialCreationOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """

        options = PublicKeyCredentialCreationOptions.from_dict(options)

        # Gather client data, RP ID from client
        client_data, rp_id = self._client_data_collector.collect_client_data(options)
        logger.debug(f"Register a new credential for RP ID: {rp_id}")

        selection = options.authenticator_selection or AuthenticatorSelectionCriteria()
        resident_key = selection.resident_key or ResidentKeyRequirement.DISCOURAGED

        enterprise_attestation = WebAuthNEnterpriseAttestation.NONE
        if options.attestation == AttestationConveyancePreference.ENTERPRISE:
            attestation = WebAuthNAttestationConveyancePreference.ANY
            if self._enterprise_rpid_list is not None:
                # Platform facilitated
                if options.rp.id in self._enterprise_rpid_list:
                    enterprise_attestation = (
                        WebAuthNEnterpriseAttestation.PLATFORM_MANAGED
                    )
            else:
                # Vendor facilitated
                enterprise_attestation = (
                    WebAuthNEnterpriseAttestation.VENDOR_FACILITATED
                )
        else:
            attestation = WebAuthNAttestationConveyancePreference.from_string(
                options.attestation or "none"
            )

        win_extensions = []
        large_blob_support = WebAuthNLargeBlobSupport.NONE
        enable_prf = False
        hmac_salts = None
        if options.extensions:
            if "credentialProtectionPolicy" in options.extensions:
                win_extensions.append(
                    WebAuthNExtension(
                        "credProtect",
                        WebAuthNCredProtectExtensionIn(
                            WebAuthNUserVerification(
                                CredProtectExtension.POLICY.str2int(
                                    options.extensions["credentialProtectionPolicy"]
                                )
                            ),
                            options.extensions.get(
                                "enforceCredentialProtectionPolicy", False
                            ),
                        ),
                    )
                )
            if "credBlob" in options.extensions:
                win_extensions.append(
                    WebAuthNExtension(
                        "credBlob",
                        WebAuthNCredBlobExtension(options.extensions["credBlob"]),
                    )
                )
            if "largeBlob" in options.extensions:
                large_blob_support = WebAuthNLargeBlobSupport.from_string(
                    options.extensions["largeBlob"].get("support", "none")
                )
            if options.extensions.get("minPinLength", True):
                win_extensions.append(WebAuthNExtension("minPinLength", BOOL(True)))
            prf = AuthenticatorExtensionsPRFInputs.from_dict(
                cast(Mapping | None, options.extensions.get("prf"))
            )
            if prf:
                enable_prf = True
                win_extensions.append(WebAuthNExtension("hmac-secret", BOOL(True)))
                if prf.eval:
                    hmac_salts = WebAuthNHmacSecretSalt(prf.eval.first, prf.eval.second)
            elif "hmacCreateSecret" in options.extensions and self._allow_hmac_secret:
                win_extensions.append(WebAuthNExtension("hmac-secret", BOOL(True)))
                hmac_get_secret = HMACGetSecretInput.from_dict(
                    cast(Mapping | None, options.extensions.get("hmacGetSecret"))
                )
                if hmac_get_secret:
                    hmac_salts = WebAuthNHmacSecretSalt(
                        hmac_get_secret.salt1, hmac_get_secret.salt2
                    )

        if event:
            timer = CancelThread(event)
            timer.start()
        else:
            timer = None

        attestation_pointer = ctypes.POINTER(WebAuthNCredentialAttestation)()
        try:
            WEBAUTHN.WebAuthNAuthenticatorMakeCredential(
                self.handle,
                ctypes.byref(WebAuthNRpEntityInformation(_as_cbor(options.rp))),
                ctypes.byref(WebAuthNUserEntityInformation(_as_cbor(options.user))),
                ctypes.byref(
                    WebAuthNCoseCredentialParameters(
                        _cbor_list(options.pub_key_cred_params)
                    )
                ),
                ctypes.byref(WebAuthNClientData(client_data)),
                ctypes.byref(
                    WebAuthNMakeCredentialOptions(
                        options.timeout or 0,
                        resident_key == ResidentKeyRequirement.REQUIRED,
                        WebAuthNAuthenticatorAttachment.from_string(
                            selection.authenticator_attachment or "any"
                        ),
                        WebAuthNUserVerificationRequirement.from_string(
                            selection.user_verification or "discouraged"
                        ),
                        attestation,
                        _cbor_list(options.exclude_credentials) or [],
                        timer.guid if timer else None,
                        enterprise_attestation,
                        large_blob_support,
                        resident_key == ResidentKeyRequirement.PREFERRED,
                        enable_prf,
                        win_extensions,
                        hmac_salts,
                        options.hints,
                    )
                ),
                ctypes.byref(attestation_pointer),
            )
        except OSError as e:
            raise ClientError.ERR.OTHER_ERROR(e)

        if timer:
            # TODO: Avoid setting event?
            timer.complete()

        obj = attestation_pointer.contents
        att_obj = AttestationObject(obj.attestation_object)

        extension_outputs: dict[str, Any] = {}
        if options.extensions:
            extensions_out = att_obj.auth_data.extensions or {}
            if obj.dwVersion >= 4 and options.extensions.get("credProps"):
                extension_outputs["credProps"] = {"rk": bool(obj.bResidentKey)}
            if "hmac-secret" in extensions_out:
                if obj.dwVersion >= 7:
                    secret = obj.pHmacSecret.contents
                    secrets = (secret.first, secret.second)
                else:
                    secrets = None
                if enable_prf:
                    extension_outputs["prf"] = {
                        "enabled": extensions_out["hmac-secret"]
                    }
                    if secrets:
                        results = {"first": secrets[0]}
                        if secrets[1]:
                            results["second"] = secrets[1]
                        extension_outputs["prf"]["results"] = results
                else:
                    extension_outputs["hmacCreateSecret"] = extensions_out[
                        "hmac-secret"
                    ]
                    if secrets:
                        results = {"output1": secrets[0]}
                        if secrets[1]:
                            results["output2"] = secrets[1]
                        extension_outputs["hmacGetSecret"] = results
            if obj.dwVersion >= 4 and "largeBlob" in options.extensions:
                extension_outputs["largeBlob"] = {
                    "supported": bool(obj.bLargeBlobSupported)
                }

        logger.info("New credential registered")

        credential = att_obj.auth_data.credential_data
        assert credential is not None  # noqa: S101

        return RegistrationResponse(
            raw_id=credential.credential_id,
            response=AuthenticatorAttestationResponse(
                client_data=client_data, attestation_object=att_obj
            ),
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
            client_extension_results=AuthenticationExtensionsClientOutputs(
                {k: _wrap_ext(k, v) for k, v in extension_outputs.items()}
            ),
            type=PublicKeyCredentialType.PUBLIC_KEY,
        )

    def get_assertion(self, options, event=None):
        """Get assertion using Windows WebAuthN APIs.

        :param options: PublicKeyCredentialRequestOptions data.
        :param threading.Event event: (optional) Signal to abort the operation.
        """

        options = PublicKeyCredentialRequestOptions.from_dict(options)

        # Gather client data, RP ID from client
        client_data, rp_id = self._client_data_collector.collect_client_data(options)
        logger.debug(f"Assert a credential for RP ID: {rp_id}")

        attachment = WebAuthNAuthenticatorAttachment.ANY
        for hint in options.hints or []:
            match hint:
                case "security-key":
                    attachment = WebAuthNAuthenticatorAttachment.CROSS_PLATFORM
                case "client-device":
                    attachment = WebAuthNAuthenticatorAttachment.PLATFORM
                case _:
                    continue
            break

        flags = 0
        large_blob = None
        large_blob_operation = WebAuthNLargeBlobOperation.NONE
        hmac_secret_salts = None
        win_extensions = []
        u2f_appid = None
        u2f_appid_used = BOOL(False)
        if options.extensions:
            if options.extensions.get("appid"):
                u2f_appid = options.extensions["appid"]
            if options.extensions.get("getCredBlob"):
                win_extensions.append(WebAuthNExtension("credBlob", BOOL(True)))
            lg_blob = AuthenticatorExtensionsLargeBlobInputs.from_dict(
                cast(Mapping | None, options.extensions.get("largeBlob"))
            )
            if lg_blob:
                if lg_blob.read:
                    large_blob_operation = WebAuthNLargeBlobOperation.GET
                else:
                    large_blob = lg_blob.write
                    large_blob_operation = WebAuthNLargeBlobOperation.SET

            prf = AuthenticatorExtensionsPRFInputs.from_dict(
                cast(Mapping | None, options.extensions.get("prf"))
            )
            if prf:
                cred_salts = prf.eval_by_credential or {}
                hmac_secret_salts = WebAuthNHmacSecretSaltValues(
                    (
                        WebAuthNHmacSecretSalt(prf.eval.first, prf.eval.second)
                        if prf.eval
                        else None
                    ),
                    [
                        WebAuthNCredWithHmacSecretSalt(
                            websafe_decode(cred_id),
                            WebAuthNHmacSecretSalt(salts.first, salts.second),
                        )
                        for cred_id, salts in cred_salts.items()
                    ],
                )
            elif "hmacGetSecret" in options.extensions and self._allow_hmac_secret:
                flags |= 0x00100000
                salts = HMACGetSecretInput.from_dict(
                    cast(Mapping, options.extensions["hmacGetSecret"])
                )
                hmac_secret_salts = WebAuthNHmacSecretSaltValues(
                    WebAuthNHmacSecretSalt(salts.salt1, salts.salt2)
                )

        if event:
            timer = CancelThread(event)
            timer.start()
        else:
            timer = None

        assertion_pointer = ctypes.POINTER(WebAuthNAssertion)()
        try:
            WEBAUTHN.WebAuthNAuthenticatorGetAssertion(
                self.handle,
                options.rp_id,
                ctypes.byref(WebAuthNClientData(client_data)),
                ctypes.byref(
                    WebAuthNGetAssertionOptions(
                        options.timeout or 0,
                        attachment,
                        WebAuthNUserVerificationRequirement.from_string(
                            options.user_verification or "discouraged"
                        ),
                        _cbor_list(options.allow_credentials) or [],
                        timer.guid if timer else None,
                        large_blob_operation,
                        large_blob,
                        hmac_secret_salts,
                        win_extensions,
                        flags,
                        u2f_appid,
                        u2f_appid_used,
                        options.hints,
                    )
                ),
                ctypes.byref(assertion_pointer),
            )
        except OSError as e:
            raise ClientError.ERR.OTHER_ERROR(e)

        if timer:
            # TODO: Avoid setting event?
            timer.complete()

        obj = assertion_pointer.contents
        auth_data = AuthenticatorData(obj.auth_data)

        extension_outputs: dict[str, Any] = {}

        if obj.dwVersion >= 2 and u2f_appid:
            extension_outputs["appid"] = bool(u2f_appid_used.value)

        if options.extensions:
            if obj.dwVersion >= 3 and hmac_secret_salts:
                secret = obj.pHmacSecret.contents
                if "prf" in options.extensions:
                    result = {"first": secret.first}
                    if secret.second:
                        result["second"] = secret.second
                    extension_outputs["prf"] = {"results": result}
                else:
                    result = {"output1": secret.first}
                    if secret.second:
                        result["output2"] = secret.second
                    extension_outputs["hmacGetSecret"] = result
            if obj.dwVersion >= 2 and obj.dwCredLargeBlobStatus != 0:
                if options.extensions["largeBlob"].get("read", False):
                    extension_outputs["largeBlob"] = {"blob": obj.cred_large_blob}
                else:
                    extension_outputs["largeBlob"] = {
                        "written": obj.dwCredLargeBlobStatus == 1
                    }

        credential = {
            "type": obj.Credential.pwszCredentialType,
            "id": obj.Credential.id,
        }
        return AssertionSelection(
            client_data,
            [
                AssertionResponse(
                    credential=credential,
                    auth_data=auth_data,
                    signature=obj.signature,
                    user={"id": obj.user_id} if obj.user_id else None,
                )
            ],
            {k: _wrap_ext(k, v) for k, v in extension_outputs.items()},
        )
