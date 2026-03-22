# Copyright (c) 2022 Yubico AB
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
import logging
from base64 import b64decode, b64encode
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date
from enum import Enum, unique
from typing import Any, Callable, Mapping, Sequence

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from .attestation import (
    Attestation,
    AttestationVerifier,
    UntrustedAttestation,
    verify_x509_chain,
)
from .cose import CoseKey
from .utils import _JsonDataObject, websafe_decode
from .webauthn import Aaguid, AttestationObject

logger = logging.getLogger(__name__)


@dataclass(eq=False, frozen=True)
class Version(_JsonDataObject):
    major: int
    minor: int


@dataclass(eq=False, frozen=True)
class RogueListEntry(_JsonDataObject):
    sk: bytes
    date: int


@dataclass(eq=False, frozen=True)
class BiometricStatusReport(_JsonDataObject):
    cert_level: int
    modality: str
    effective_date: int
    certification_descriptor: str
    certificate_number: str
    certification_policy_version: str
    certification_requirements_version: str


@dataclass(eq=False, frozen=True)
class CodeAccuracyDescriptor(_JsonDataObject):
    base: int
    min_length: int
    max_retries: int | None = None
    block_slowdown: int | None = None


@dataclass(eq=False, frozen=True)
class BiometricAccuracyDescriptor(_JsonDataObject):
    self_attested_frr: float | None = field(
        default=None, metadata=dict(name="selfAttestedFRR")
    )
    self_attested_far: float | None = field(
        default=None, metadata=dict(name="selfAttestedFAR")
    )
    iapar_threshold: float | None = field(
        default=None, metadata=dict(name="iAPARThreshold")
    )
    max_templates: int | None = None
    max_retries: int | None = None
    block_slowdown: int | None = None


@dataclass(eq=False, frozen=True)
class PatternAccuracyDescriptor(_JsonDataObject):
    min_complexity: int
    max_retries: int | None = None
    block_slowdown: int | None = None


@dataclass(eq=False, frozen=True)
class VerificationMethodDescriptor(_JsonDataObject):
    user_verification_method: str | None = None
    ca_desc: CodeAccuracyDescriptor | None = None
    ba_desc: BiometricAccuracyDescriptor | None = None
    pa_desc: PatternAccuracyDescriptor | None = None


@dataclass(eq=False, frozen=True)
class RgbPaletteEntry(_JsonDataObject):
    r: int
    g: int
    b: int


@dataclass(eq=False, frozen=True)
class DisplayPngCharacteristicsDescriptor(_JsonDataObject):
    width: int
    height: int
    bit_depth: int
    color_type: int
    compression: int
    filter: int
    interlace: int
    plte: Sequence[RgbPaletteEntry] | None = None


@dataclass(eq=False, frozen=True)
class EcdaaTrustAnchor(_JsonDataObject):
    x: str = field(metadata=dict(name="X"))
    y: str = field(metadata=dict(name="Y"))
    c: str
    sx: str
    sy: str
    g1_curve: str = field(metadata=dict(name="G1Curve"))


@unique
class AuthenticatorStatus(str, Enum):
    """Status of an Authenticator."""

    NOT_FIDO_CERTIFIED = "NOT_FIDO_CERTIFIED"
    FIDO_CERTIFIED = "FIDO_CERTIFIED"
    USER_VERIFICATION_BYPASS = "USER_VERIFICATION_BYPASS"
    ATTESTATION_KEY_COMPROMISE = "ATTESTATION_KEY_COMPROMISE"
    USER_KEY_REMOTE_COMPROMISE = "USER_KEY_REMOTE_COMPROMISE"
    USER_KEY_PHYSICAL_COMPROMISE = "USER_KEY_PHYSICAL_COMPROMISE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    RETIRED = "RETIRED"
    REVOKED = "REVOKED"
    SELF_ASSERTION_SUBMITTED = "SELF_ASSERTION_SUBMITTED"
    FIDO_CERTIFIED_L1 = "FIDO_CERTIFIED_L1"
    FIDO_CERTIFIED_L1plus = "FIDO_CERTIFIED_L1plus"
    FIDO_CERTIFIED_L2 = "FIDO_CERTIFIED_L2"
    FIDO_CERTIFIED_L2plus = "FIDO_CERTIFIED_L2plus"
    FIDO_CERTIFIED_L3 = "FIDO_CERTIFIED_L3"
    FIDO_CERTIFIED_L3plus = "FIDO_CERTIFIED_L3plus"
    FIPS140_CERTIFIED_L1 = "FIPS140_CERTIFIED_L1"
    FIPS140_CERTIFIED_L2 = "FIPS140_CERTIFIED_L2"
    FIPS140_CERTIFIED_L3 = "FIPS140_CERTIFIED_L3"
    FIPS140_CERTIFIED_L4 = "FIPS140_CERTIFIED_L4"


@dataclass(eq=False, frozen=True)
class StatusReport(_JsonDataObject):
    status: AuthenticatorStatus
    effective_date: date | None = field(
        metadata=dict(
            deserialize=date.fromisoformat,
            serialize=lambda x: x.isoformat(),
        ),
        default=None,
    )
    authenticator_version: int | None = None
    batch_certificate: bytes | None = field(
        metadata=dict(deserialize=b64decode, serialize=lambda x: b64encode(x).decode()),
        default=None,
    )
    certificate: bytes | None = field(
        metadata=dict(deserialize=b64decode, serialize=lambda x: b64encode(x).decode()),
        default=None,
    )
    url: str | None = None
    certification_descriptor: str | None = None
    certificate_number: str | None = None
    certification_policy_version: str | None = None
    certification_profiles: Sequence[str] | None = None
    certification_requirements_version: str | None = None
    sunset_date: date | None = field(
        metadata=dict(
            deserialize=date.fromisoformat,
            serialize=lambda x: x.isoformat(),
        ),
        default=None,
    )
    fips_revision: int | None = None
    fips_physical_security_level: int | None = None


@dataclass(eq=False, frozen=True)
class ExtensionDescriptor(_JsonDataObject):
    fail_if_unknown: bool = field(metadata=dict(name="fail_if_unknown"))
    id: str
    tag: int | None = None
    data: str | None = None


@dataclass(eq=False, frozen=True)
class MetadataStatement(_JsonDataObject):
    description: str
    authenticator_version: int
    schema: int
    upv: Sequence[Version]
    attestation_types: Sequence[str]
    user_verification_details: Sequence[Sequence[VerificationMethodDescriptor]] = field(
        metadata=dict(serialize=lambda xss: [[dict(x) for x in xs] for xs in xss])
    )
    key_protection: Sequence[str]
    matcher_protection: Sequence[str]
    attachment_hint: Sequence[str]
    tc_display: Sequence[str]
    attestation_root_certificates: Sequence[bytes] = field(
        metadata=dict(
            deserialize=lambda xs: [b64decode(x) for x in xs],
            serialize=lambda xs: [b64encode(x).decode() for x in xs],
        )
    )
    legal_header: str | None = None
    aaid: str | None = None
    aaguid: Aaguid | None = field(
        metadata=dict(
            deserialize=Aaguid.parse,
            serialize=lambda x: str(x),
        ),
        default=None,
    )
    attestation_certificate_key_identifiers: Sequence[bytes] | None = field(
        metadata=dict(
            deserialize=lambda xs: [bytes.fromhex(x) for x in xs],
            serialize=lambda xs: [x.hex() for x in xs],
        ),
        default=None,
    )
    friendly_names: Mapping[str, str] | None = None
    alternative_descriptions: Mapping[str, str] | None = None
    protocol_family: str | None = None
    authentication_algorithms: Sequence[str] | None = None
    public_key_alg_and_encodings: Sequence[str] | None = None
    is_key_restricted: bool | None = None
    is_fresh_user_verification_required: bool | None = None
    crypto_strength: int | None = None
    operating_env: str | None = None
    tc_display_content_type: str | None = None
    tc_display_png_characteristics: (
        Sequence[DisplayPngCharacteristicsDescriptor] | None
    ) = field(
        metadata=dict(name="tcDisplayPNGCharacteristics"),
        default=None,
    )
    ecdaa_trust_anchors: Sequence[EcdaaTrustAnchor] | None = None
    icon: str | None = None
    icon_dark: str | None = None
    provider_logo_light: str | None = None
    provider_logo_dark: str | None = None
    supported_extensions: Sequence[ExtensionDescriptor] | None = None
    multi_device_credential_support: str | None = None
    authenticator_get_info: Mapping[str, Any] | None = None
    cx_config_url: str | None = field(metadata=dict(name="cxConfigURL"), default=None)


@dataclass(eq=False, frozen=True)
class MetadataBlobPayloadEntry(_JsonDataObject):
    status_reports: Sequence[StatusReport]
    time_of_last_status_change: date = field(
        metadata=dict(
            deserialize=date.fromisoformat,
            serialize=lambda x: x.isoformat(),
        )
    )
    aaid: str | None = None
    aaguid: Aaguid | None = field(
        metadata=dict(
            deserialize=Aaguid.parse,
            serialize=lambda x: str(x),
        ),
        default=None,
    )
    attestation_certificate_key_identifiers: Sequence[bytes] | None = field(
        metadata=dict(
            deserialize=lambda xs: [bytes.fromhex(x) for x in xs],
            serialize=lambda xs: [x.hex() for x in xs],
        ),
        default=None,
    )
    metadata_statement: MetadataStatement | None = None
    biometric_status_reports: Sequence[BiometricStatusReport] | None = None
    rogue_list_url: str | None = field(metadata=dict(name="rogueListURL"), default=None)
    rogue_list_hash: bytes | None = field(
        metadata=dict(
            deserialize=bytes.fromhex,
            serialize=lambda x: x.hex(),
        ),
        default=None,
    )


@dataclass(eq=False, frozen=True)
class MetadataBlobPayload(_JsonDataObject):
    legal_header: str
    no: int
    next_update: date = field(
        metadata=dict(
            deserialize=date.fromisoformat,
            serialize=lambda x: x.isoformat(),
        )
    )
    entries: Sequence[MetadataBlobPayloadEntry]


EntryFilter = Callable[[MetadataBlobPayloadEntry], bool]
LookupFilter = Callable[[MetadataBlobPayloadEntry, Sequence[bytes]], bool]


def filter_revoked(entry: MetadataBlobPayloadEntry) -> bool:
    """Filters out any revoked metadata entry.

    This filter will remove any metadata entry which has a status_report with
    the REVOKED status.
    """
    return not any(
        r.status == AuthenticatorStatus.REVOKED for r in entry.status_reports
    )


def filter_attestation_key_compromised(
    entry: MetadataBlobPayloadEntry, certificate_chain: Sequence[bytes]
) -> bool:
    """Denies any attestation that has a compromised attestation key.

    This filter checks the status reports of a metadata entry and ensures the
    attestation isn't signed by a key which is marked as compromised.
    """
    for r in entry.status_reports:
        if r.status == AuthenticatorStatus.ATTESTATION_KEY_COMPROMISE:
            if r.certificate in certificate_chain:
                return False
    return True


_last_entry: ContextVar[MetadataBlobPayloadEntry | None] = ContextVar("_last_entry")


class MdsAttestationVerifier(AttestationVerifier):
    """MDS3 implementation of an AttestationVerifier.

    The entry_filter is an optional predicate used to filter which metadata entries to
    include in the lookup for verification. By default, a filter that removes any
    entries that have a status report indicating the authenticator is REVOKED is used.
    See: filter_revoked

    The attestation_filter is an optional predicate used to filter metadata entries
    while performing attestation validation, and may take into account the
    Authenticators attestation trust_chain. By default, a filter that will fail any
    verification that has a trust_chain where one of the certificates is marked as
    compromised by the metadata statement is used.
    See: filter_attestation_key_compromised

    NOTE: The attestation_filter is not used when calling find_entry_by_aaguid nor
    find_entry_by_chain as no attestation is being verified!

    Setting either filter (including setting it to None) will replace it, removing
    the default behavior.

    :param blob: The MetadataBlobPayload to query for device metadata.
    :param entry_filter: An optional filter to exclude entries from lookup.
    :param attestation_filter: An optional filter to fail verification for a given
        attestation.
    :param attestation_types: A list of Attestation types to support.
    """

    def __init__(
        self,
        blob: MetadataBlobPayload,
        entry_filter: EntryFilter | None = filter_revoked,
        attestation_filter: LookupFilter | None = filter_attestation_key_compromised,
        attestation_types: Sequence[Attestation] | None = None,
    ):
        super().__init__(attestation_types)
        self._attestation_filter = attestation_filter or (
            lambda a, b: True
        )  # No-op for None

        entries = (
            [e for e in blob.entries if entry_filter(e)]
            if entry_filter
            else blob.entries
        )
        self._aaguid_table = {e.aaguid: e for e in entries if e.aaguid}
        self._ski_table = {
            ski: e
            for e in entries
            for ski in e.attestation_certificate_key_identifiers or []
        }

    def find_entry_by_aaguid(self, aaguid: Aaguid) -> MetadataBlobPayloadEntry | None:
        """Find an entry by AAGUID.

        Returns a MetadataBlobPayloadEntry with a matching aaguid field, if found.
        This method does not take the attestation_filter into account.
        """
        return self._aaguid_table.get(aaguid)

    def find_entry_by_chain(
        self, certificate_chain: Sequence[bytes]
    ) -> MetadataBlobPayloadEntry | None:
        """Find an entry by trust chain.

        Returns a MetadataBlobPayloadEntry containing an
        attestationCertificateKeyIdentifier which matches one of the certificates in the
        given chain, if found.
        This method does not take the attestation_filter into account.
        """
        for der in certificate_chain:
            cert = x509.load_der_x509_certificate(der, default_backend())
            ski = x509.SubjectKeyIdentifier.from_public_key(cert.public_key()).digest
            if ski in self._ski_table:
                return self._ski_table[ski]
        return None

    def ca_lookup(self, attestation_result, auth_data):
        assert auth_data.credential_data is not None  # noqa: S101
        aaguid = auth_data.credential_data.aaguid
        if aaguid:
            logging.debug(f"Using AAGUID: {aaguid} to look up metadata")
            entry = self.find_entry_by_aaguid(aaguid)
        else:
            logging.debug("Using trust_path chain to look up metadata")
            entry = self.find_entry_by_chain(attestation_result.trust_path)

        if entry:
            logging.debug(f"Found entry: {entry}")

            # Check attestation filter
            if not self._attestation_filter(entry, attestation_result.trust_path):
                logging.debug("Matched entry did not pass attestation filter")
                return None

            # Figure out which root to use
            if not entry.metadata_statement:
                logging.warning(
                    "Matched entry has no metadata_statement, can't validate!"
                )
                return None

            issuer = x509.load_der_x509_certificate(
                attestation_result.trust_path[-1], default_backend()
            ).issuer

            for root in entry.metadata_statement.attestation_root_certificates:
                subject = x509.load_der_x509_certificate(
                    root, default_backend()
                ).subject
                if subject == issuer:
                    _last_entry.set(entry)
                    return root
            logger.info(f"No attestation root matching subject: {issuer}")
        return None

    def find_entry(
        self, attestation_object: AttestationObject, client_data_hash: bytes
    ) -> MetadataBlobPayloadEntry | None:
        """Lookup a Metadata entry based on an Attestation.

        Returns the first Metadata entry matching the given attestation and verifies it,
        including checking it against the attestation_filter.
        """
        token = _last_entry.set(None)
        try:
            self.verify_attestation(attestation_object, client_data_hash)
            return _last_entry.get()
        except UntrustedAttestation:
            return None
        finally:
            _last_entry.reset(token)


def parse_blob(blob: bytes, trust_root: bytes | None) -> MetadataBlobPayload:
    """Parse a FIDO MDS3 blob and verifies its signature.

    See https://fidoalliance.org/metadata/ for details on obtaining the blob, as well as
    the CA certificate used to sign it.

    The resulting MetadataBlobPayload can be used to lookup metadata entries for
    specific Authenticators, or used with the MdsAttestationVerifier to verify that the
    attestation from a WebAuthn registration is valid and included in the metadata blob.

    NOTE: If trust_root is None, the signature of the blob will NOT be verified!
    """
    message, signature_b64 = blob.rsplit(b".", 1)
    signature = websafe_decode(signature_b64)
    header, payload = (json.loads(websafe_decode(x)) for x in message.split(b"."))

    if trust_root is not None:
        # Verify trust chain
        chain = [b64decode(c) for c in header.get("x5c", [])]
        chain += [trust_root]
        verify_x509_chain(chain)

        # Verify blob signature using leaf
        leaf = x509.load_der_x509_certificate(chain[0], default_backend())
        public_key = CoseKey.for_name(header["alg"]).from_cryptography_key(
            leaf.public_key()
        )
        public_key.verify(message, signature)
    else:
        logger.warning(
            "Parsing MDS blob without trust anchor, CONTENT IS NOT VERIFIED!"
        )

    return MetadataBlobPayload.from_dict(payload)
