from enum import Enum

from pyasn1.type import tag
from pyasn1.type.namedtype import NamedTypes, NamedType, OptionalNamedType
from pyasn1.type.namedval import NamedValues
from pyasn1.type.univ import (
    Boolean,
    Enumerated,
    Integer,
    Null,
    OctetString,
    Sequence,
    SetOf,
)


class Integers(SetOf):
    # type error ignored due to https://github.com/python/typeshed/issues/15369
    componentType = Integer()  # type: ignore


class SecurityLevel(Enumerated):
    namedValues = NamedValues(
        ("Software", 0),
        ("TrustedEnvironment", 1),
        ("StrongBox", 2),
    )


class VerifiedBootState(Enumerated):
    namedValues = NamedValues(
        ("Verified", 0),
        ("SelfSigned", 1),
        ("Unverified", 2),
        ("Failed", 3),
    )


class RootOfTrust(Sequence):
    componentType = NamedTypes(
        NamedType("verifiedBootKey", OctetString()),
        NamedType("deviceLocked", Boolean()),
        NamedType("verifiedBootState", VerifiedBootState()),
        NamedType("verifiedBootHash", OctetString()),
    )


class AuthorizationList(Sequence):
    componentType = NamedTypes(
        OptionalNamedType(
            "purpose",
            Integers().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 1)
            ),
        ),
        OptionalNamedType(
            "algorithm",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 2)
            ),
        ),
        OptionalNamedType(
            "keySize",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 3)
            ),
        ),
        OptionalNamedType(
            "digest",
            Integers().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 5)
            ),
        ),
        OptionalNamedType(
            "padding",
            Integers().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 6)
            ),
        ),
        OptionalNamedType(
            "ecCurve",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 10)
            ),
        ),
        OptionalNamedType(
            "rsaPublicExponent",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 200)
            ),
        ),
        OptionalNamedType(
            "rollbackResistance",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 303)
            ),
        ),
        OptionalNamedType(
            "activeDateTime",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 400)
            ),
        ),
        OptionalNamedType(
            "originationExpireDateTime",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 401)
            ),
        ),
        OptionalNamedType(
            "usageExpireDateTime",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 402)
            ),
        ),
        OptionalNamedType(
            "noAuthRequired",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 503)
            ),
        ),
        OptionalNamedType(
            "userAuthType",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 504)
            ),
        ),
        OptionalNamedType(
            "authTimeout",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 505)
            ),
        ),
        OptionalNamedType(
            "allowWhileOnBody",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 506)
            ),
        ),
        OptionalNamedType(
            "trustedUserPresenceRequired",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 507)
            ),
        ),
        OptionalNamedType(
            "trustedConfirmationRequired",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 508)
            ),
        ),
        OptionalNamedType(
            "unlockedDeviceRequired",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 509)
            ),
        ),
        OptionalNamedType(
            "allApplications",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 600)
            ),
        ),
        OptionalNamedType(
            "applicationId",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 601)
            ),
        ),
        OptionalNamedType(
            "creationDateTime",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 701)
            ),
        ),
        OptionalNamedType(
            "origin",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 702)
            ),
        ),
        OptionalNamedType(
            "rollbackResistant",
            Null().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 703)
            ),
        ),
        OptionalNamedType(
            "rootOfTrust",
            RootOfTrust().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 704)
            ),
        ),
        OptionalNamedType(
            "osVersion",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 705)
            ),
        ),
        OptionalNamedType(
            "osPatchLevel",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 706)
            ),
        ),
        OptionalNamedType(
            "attestationApplicationId",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 709)
            ),
        ),
        OptionalNamedType(
            "attestationIdBrand",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 710)
            ),
        ),
        OptionalNamedType(
            "attestationIdDevice",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 711)
            ),
        ),
        OptionalNamedType(
            "attestationIdProduct",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 712)
            ),
        ),
        OptionalNamedType(
            "attestationIdSerial",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 713)
            ),
        ),
        OptionalNamedType(
            "attestationIdImei",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 714)
            ),
        ),
        OptionalNamedType(
            "attestationIdMeid",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 715)
            ),
        ),
        OptionalNamedType(
            "attestationIdManufacturer",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 716)
            ),
        ),
        OptionalNamedType(
            "attestationIdModel",
            OctetString().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 717)
            ),
        ),
        OptionalNamedType(
            "vendorPatchLevel",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 718)
            ),
        ),
        OptionalNamedType(
            "bootPatchLevel",
            Integer().subtype(
                explicitTag=tag.Tag(tag.tagClassContext, tag.tagFormatSimple, 719)
            ),
        ),
    )


class KeyDescription(Sequence):
    """Attestation extension content as ASN.1 schema (DER-encoded)

    Corresponds to X.509 certificate extension with the following OID:

    `1.3.6.1.4.1.11129.2.1.17`

    See https://source.android.com/security/keystore/attestation#schema
    """

    componentType = NamedTypes(
        NamedType("attestationVersion", Integer()),
        NamedType("attestationSecurityLevel", SecurityLevel()),
        NamedType("keymasterVersion", Integer()),
        NamedType("keymasterSecurityLevel", SecurityLevel()),
        NamedType("attestationChallenge", OctetString()),
        NamedType("uniqueId", OctetString()),
        NamedType("softwareEnforced", AuthorizationList()),
        NamedType("teeEnforced", AuthorizationList()),
    )


class KeyOrigin(int, Enum):
    """`Tag::ORIGIN`

    See https://source.android.com/security/keystore/tags#origin
    """

    GENERATED = 0
    DERIVED = 1
    IMPORTED = 2
    UNKNOWN = 3


class KeyPurpose(int, Enum):
    """`Tag::PURPOSE`

    See https://source.android.com/security/keystore/tags#purpose
    """

    ENCRYPT = 0
    DECRYPT = 1
    SIGN = 2
    VERIFY = 3
    DERIVE_KEY = 4
    WRAP_KEY = 5
