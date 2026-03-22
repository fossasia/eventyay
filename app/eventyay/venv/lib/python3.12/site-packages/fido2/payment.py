# Copyright (c) 2025 Yubico AB
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

from dataclasses import dataclass

from .client import DefaultClientDataCollector
from .ctap2.extensions import (
    AuthenticationExtensionsPaymentInputs,
    PaymentCredentialInstrument,
    PaymentCurrencyAmount,
)
from .utils import _JsonDataObject
from .webauthn import (
    AuthenticatorAttachment,
    CollectedClientData,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialRequestOptions,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

"""
Implements client and server functionality for the WebAuthn "payment" extension.

https://www.w3.org/TR/secure-payment-confirmation/#sctn-payment-extension-registration
"""


@dataclass(eq=False, frozen=True, kw_only=True)
class CollectedClientAdditionalPaymentData(_JsonDataObject):
    rp_id: str
    top_origin: str
    payee_name: str | None = None
    payee_origin: str | None = None
    total: PaymentCurrencyAmount
    instrument: PaymentCredentialInstrument


@dataclass(init=False, frozen=True, kw_only=True)
class CollectedClientPaymentData(CollectedClientData):
    payment: CollectedClientAdditionalPaymentData

    def __init__(self, serialized: bytes):
        super().__init__(serialized)

        payment = CollectedClientAdditionalPaymentData.from_dict(self._data["payment"])
        object.__setattr__(self, "payment", payment)

    @classmethod
    def create(
        cls,
        type: str,
        challenge: bytes | str,
        origin: str,
        cross_origin: bool = False,
        **kwargs,
    ) -> CollectedClientData:
        return super().create(
            type=type,
            challenge=challenge,
            origin=origin,
            cross_origin=cross_origin,
            payment=dict(kwargs.pop("payment")),
            **kwargs,
        )


class PaymentClientDataCollector(DefaultClientDataCollector):
    """ClientDataCollector for the WebAuthn "payment" extension.

    This class can be used together with the CTAP2 "thirdPartyPayment" extension to
    enable third-party payment confirmation. It collects the necessary client data and
    validates the options provided by the client.
    """

    def collect_client_data(self, options):
        # Get the effective RP ID from the request options, falling back to the origin
        rp_id = self.get_rp_id(options, self._origin)
        inputs = options.extensions or {}
        data = AuthenticationExtensionsPaymentInputs.from_dict(inputs.get("payment"))
        if data and data.is_payment:
            if isinstance(options, PublicKeyCredentialCreationOptions):
                sel = options.authenticator_selection
                if (
                    not sel
                    or sel.authenticator_attachment
                    not in (
                        AuthenticatorAttachment.PLATFORM,
                        # This is against the spec, but we need cross-platform
                        AuthenticatorAttachment.CROSS_PLATFORM,
                    )
                    or sel.resident_key
                    not in (
                        ResidentKeyRequirement.REQUIRED,
                        ResidentKeyRequirement.PREFERRED,
                    )
                    or sel.user_verification != UserVerificationRequirement.REQUIRED
                ):
                    raise ValueError("Invalid options for payment extension")
            elif isinstance(options, PublicKeyCredentialRequestOptions):
                # NOTE: We skip RP ID validation, as per the spec
                return (
                    CollectedClientPaymentData.create(
                        type="payment.get",
                        origin=self._origin,
                        challenge=options.challenge,
                        payment=CollectedClientAdditionalPaymentData(
                            rp_id=data.rp_id,
                            top_origin=data.top_origin,
                            payee_name=data.payee_name,
                            payee_origin=data.payee_origin,
                            total=data.total,
                            instrument=data.instrument,
                        ),
                    ),
                    rp_id,
                )

        # Validate that the RP ID is valid for the given origin
        self.verify_rp_id(rp_id, self._origin)
        return super().collect_client_data(options)
