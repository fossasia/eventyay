# Copyright (C) 2015  JWCrypto Project Contributors - see LICENSE file

import unittest

from jwcrypto import jwe
from jwcrypto import jwk
from jwcrypto import jws
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.common import json_decode, json_encode

# Based on: RFC 7520

EC_Public_Key_3_1 = {
    "kty": "EC",
    "kid": "bilbo.baggins@hobbiton.example",
    "use": "sig",
    "crv": "P-521",
    "x": "AHKZLLOsCOzz5cY97ewNUajB957y-C-U88c3v13nmGZx6sYl_oJXu9"
         "A5RkTKqjqvjyekWF-7ytDyRXYgCF5cj0Kt",
    "y": "AdymlHvOiLxXkEhayXQnNCvDX4h9htZaCJN34kfmC6pV5OhQHiraVy"
         "SsUdaQkAgDPrwQrJmbnX9cwlGfP-HqHZR1"}

EC_Private_Key_3_2 = {
    "kty": "EC",
    "kid": "bilbo.baggins@hobbiton.example",
    "use": "sig",
    "crv": "P-521",
    "x": "AHKZLLOsCOzz5cY97ewNUajB957y-C-U88c3v13nmGZx6sYl_oJXu9"
         "A5RkTKqjqvjyekWF-7ytDyRXYgCF5cj0Kt",
    "y": "AdymlHvOiLxXkEhayXQnNCvDX4h9htZaCJN34kfmC6pV5OhQHiraVy"
         "SsUdaQkAgDPrwQrJmbnX9cwlGfP-HqHZR1",
    "d": "AAhRON2r9cqXX1hg-RoI6R1tX5p2rUAYdmpHZoC1XNM56KtscrX6zb"
         "KipQrCW9CGZH3T4ubpnoTKLDYJ_fF3_rJt"}

RSA_Public_Key_3_3 = {
    "kty": "RSA",
    "kid": "bilbo.baggins@hobbiton.example",
    "use": "sig",
    "n": "n4EPtAOCc9AlkeQHPzHStgAbgs7bTZLwUBZdR8_KuKPEHLd4rHVTeT"
         "-O-XV2jRojdNhxJWTDvNd7nqQ0VEiZQHz_AJmSCpMaJMRBSFKrKb2wqV"
         "wGU_NsYOYL-QtiWN2lbzcEe6XC0dApr5ydQLrHqkHHig3RBordaZ6Aj-"
         "oBHqFEHYpPe7Tpe-OfVfHd1E6cS6M1FZcD1NNLYD5lFHpPI9bTwJlsde"
         "3uhGqC0ZCuEHg8lhzwOHrtIQbS0FVbb9k3-tVTU4fg_3L_vniUFAKwuC"
         "LqKnS2BYwdq_mzSnbLY7h_qixoR7jig3__kRhuaxwUkRz5iaiQkqgc5g"
         "HdrNP5zw",
    "e": "AQAB"}

RSA_Private_Key_3_4 = {
    "kty": "RSA",
    "kid": "bilbo.baggins@hobbiton.example",
    "use": "sig",
    "n": "n4EPtAOCc9AlkeQHPzHStgAbgs7bTZLwUBZdR8_KuKPEHLd4rHVTeT"
         "-O-XV2jRojdNhxJWTDvNd7nqQ0VEiZQHz_AJmSCpMaJMRBSFKrKb2wqV"
         "wGU_NsYOYL-QtiWN2lbzcEe6XC0dApr5ydQLrHqkHHig3RBordaZ6Aj-"
         "oBHqFEHYpPe7Tpe-OfVfHd1E6cS6M1FZcD1NNLYD5lFHpPI9bTwJlsde"
         "3uhGqC0ZCuEHg8lhzwOHrtIQbS0FVbb9k3-tVTU4fg_3L_vniUFAKwuC"
         "LqKnS2BYwdq_mzSnbLY7h_qixoR7jig3__kRhuaxwUkRz5iaiQkqgc5g"
         "HdrNP5zw",
    "e": "AQAB",
    "d": "bWUC9B-EFRIo8kpGfh0ZuyGPvMNKvYWNtB_ikiH9k20eT-O1q_I78e"
         "iZkpXxXQ0UTEs2LsNRS-8uJbvQ-A1irkwMSMkK1J3XTGgdrhCku9gRld"
         "Y7sNA_AKZGh-Q661_42rINLRCe8W-nZ34ui_qOfkLnK9QWDDqpaIsA-b"
         "MwWWSDFu2MUBYwkHTMEzLYGqOe04noqeq1hExBTHBOBdkMXiuFhUq1BU"
         "6l-DqEiWxqg82sXt2h-LMnT3046AOYJoRioz75tSUQfGCshWTBnP5uDj"
         "d18kKhyv07lhfSJdrPdM5Plyl21hsFf4L_mHCuoFau7gdsPfHPxxjVOc"
         "OpBrQzwQ",
    "p": "3Slxg_DwTXJcb6095RoXygQCAZ5RnAvZlno1yhHtnUex_fp7AZ_9nR"
         "aO7HX_-SFfGQeutao2TDjDAWU4Vupk8rw9JR0AzZ0N2fvuIAmr_WCsmG"
         "peNqQnev1T7IyEsnh8UMt-n5CafhkikzhEsrmndH6LxOrvRJlsPp6Zv8"
         "bUq0k",
    "q": "uKE2dh-cTf6ERF4k4e_jy78GfPYUIaUyoSSJuBzp3Cubk3OCqs6grT"
         "8bR_cu0Dm1MZwWmtdqDyI95HrUeq3MP15vMMON8lHTeZu2lmKvwqW7an"
         "V5UzhM1iZ7z4yMkuUwFWoBvyY898EXvRD-hdqRxHlSqAZ192zB3pVFJ0"
         "s7pFc",
    "dp": "B8PVvXkvJrj2L-GYQ7v3y9r6Kw5g9SahXBwsWUzp19TVlgI-YV85q"
          "1NIb1rxQtD-IsXXR3-TanevuRPRt5OBOdiMGQp8pbt26gljYfKU_E9xn"
          "-RULHz0-ed9E9gXLKD4VGngpz-PfQ_q29pk5xWHoJp009Qf1HvChixRX"
          "59ehik",
    "dq": "CLDmDGduhylc9o7r84rEUVn7pzQ6PF83Y-iBZx5NT-TpnOZKF1pEr"
          "AMVeKzFEl41DlHHqqBLSM0W1sOFbwTxYWZDm6sI6og5iTbwQGIC3gnJK"
          "bi_7k_vJgGHwHxgPaX2PnvP-zyEkDERuf-ry4c_Z11Cq9AqC2yeL6kdK"
          "T1cYF8",
    "qi": "3PiqvXQN0zwMeE-sBvZgi289XP9XCQF3VWqPzMKnIgQp7_Tugo6-N"
          "ZBKCQsMf3HaEGBjTVJs_jcK8-TRXvaKe-7ZMaQj8VfBdYkssbu0NKDDh"
          "jJ-GtiseaDVWt7dcH0cfwxgFUHpQh7FoCrjFJ6h6ZEpMF6xmujs4qMpP"
          "z8aaI4"}

Symmetric_Key_MAC_3_5 = {
    "kty": "oct",
    "kid": "018c0ae5-4d9b-471b-bfd6-eef314bc7037",
    "use": "sig",
    "alg": "HS256",
    "k": "hJtXIZ2uSN5kbQfbtTNWbpdmhkV8FJG-Onbc6mxCcYg"}

Symmetric_Key_Enc_3_6 = {
    "kty": "oct",
    "kid": "1e571774-2e08-40da-8308-e8d68773842d",
    "use": "enc",
    "alg": "A256GCM",
    "k": "AAPapAv4LbFbiVawEjagUBluYqN5rhna-8nuldDvOx8"}

Payload_plaintext_b64_4 = \
    "SXTigJlzIGEgZGFuZ2Vyb3VzIGJ1c2luZXNzLCBGcm9kbywgZ29pbmcgb3V0IH" + \
    "lvdXIgZG9vci4gWW91IHN0ZXAgb250byB0aGUgcm9hZCwgYW5kIGlmIHlvdSBk" + \
    "b24ndCBrZWVwIHlvdXIgZmVldCwgdGhlcmXigJlzIG5vIGtub3dpbmcgd2hlcm" + \
    "UgeW91IG1pZ2h0IGJlIHN3ZXB0IG9mZiB0by4"

# 4.1
JWS_Protected_Header_4_1_2 = \
    "eyJhbGciOiJSUzI1NiIsImtpZCI6ImJpbGJvLmJhZ2dpbnNAaG9iYml0b24uZX" + \
    "hhbXBsZSJ9"

JWS_Signature_4_1_2 = \
    "MRjdkly7_-oTPTS3AXP41iQIGKa80A0ZmTuV5MEaHoxnW2e5CZ5NlKtainoFmK" + \
    "ZopdHM1O2U4mwzJdQx996ivp83xuglII7PNDi84wnB-BDkoBwA78185hX-Es4J" + \
    "IwmDLJK3lfWRa-XtL0RnltuYv746iYTh_qHRD68BNt1uSNCrUCTJDt5aAE6x8w" + \
    "W1Kt9eRo4QPocSadnHXFxnt8Is9UzpERV0ePPQdLuW3IS_de3xyIrDaLGdjluP" + \
    "xUAhb6L2aXic1U12podGU0KLUQSE_oI-ZnmKJ3F4uOZDnd6QZWJushZ41Axf_f" + \
    "cIe8u9ipH84ogoree7vjbU5y18kDquDg"

JWS_compact_4_1_3 = \
    "%s.%s.%s" % (JWS_Protected_Header_4_1_2,
                  Payload_plaintext_b64_4,
                  JWS_Signature_4_1_2)

JWS_general_4_1_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "protected": JWS_Protected_Header_4_1_2,
        "signature": JWS_Signature_4_1_2}]}

JWS_flattened_4_1_3 = {
    "payload": Payload_plaintext_b64_4,
    "protected": JWS_Protected_Header_4_1_2,
    "signature": JWS_Signature_4_1_2}

# 4.2
JWS_Protected_Header_4_2_2 = \
    "eyJhbGciOiJQUzM4NCIsImtpZCI6ImJpbGJvLmJhZ2dpbnNAaG9iYml0b24uZX" + \
    "hhbXBsZSJ9"

JWS_Signature_4_2_2 = \
    "cu22eBqkYDKgIlTpzDXGvaFfz6WGoz7fUDcfT0kkOy42miAh2qyBzk1xEsnk2I" + \
    "pN6-tPid6VrklHkqsGqDqHCdP6O8TTB5dDDItllVo6_1OLPpcbUrhiUSMxbbXU" + \
    "vdvWXzg-UD8biiReQFlfz28zGWVsdiNAUf8ZnyPEgVFn442ZdNqiVJRmBqrYRX" + \
    "e8P_ijQ7p8Vdz0TTrxUeT3lm8d9shnr2lfJT8ImUjvAA2Xez2Mlp8cBE5awDzT" + \
    "0qI0n6uiP1aCN_2_jLAeQTlqRHtfa64QQSUmFAAjVKPbByi7xho0uTOcbH510a" + \
    "6GYmJUAfmWjwZ6oD4ifKo8DYM-X72Eaw"

JWS_compact_4_2_3 = \
    "%s.%s.%s" % (JWS_Protected_Header_4_2_2,
                  Payload_plaintext_b64_4,
                  JWS_Signature_4_2_2)

JWS_general_4_2_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "protected": JWS_Protected_Header_4_2_2,
        "signature": JWS_Signature_4_2_2}]}

JWS_flattened_4_2_3 = {
    "payload": Payload_plaintext_b64_4,
    "protected": JWS_Protected_Header_4_2_2,
    "signature": JWS_Signature_4_2_2}

# 4.3
JWS_Protected_Header_4_3_2 = \
    "eyJhbGciOiJFUzUxMiIsImtpZCI6ImJpbGJvLmJhZ2dpbnNAaG9iYml0b24uZX" + \
    "hhbXBsZSJ9"

JWS_Signature_4_3_2 = \
    "AE_R_YZCChjn4791jSQCrdPZCNYqHXCTZH0-JZGYNlaAjP2kqaluUIIUnC9qvb" + \
    "u9Plon7KRTzoNEuT4Va2cmL1eJAQy3mtPBu_u_sDDyYjnAMDxXPn7XrT0lw-kv" + \
    "AD890jl8e2puQens_IEKBpHABlsbEPX6sFY8OcGDqoRuBomu9xQ2"

JWS_compact_4_3_3 = \
    "%s.%s.%s" % (JWS_Protected_Header_4_3_2,
                  Payload_plaintext_b64_4,
                  JWS_Signature_4_3_2)

JWS_general_4_3_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "protected": JWS_Protected_Header_4_3_2,
        "signature": JWS_Signature_4_3_2}]}

JWS_flattened_4_3_3 = {
    "payload": Payload_plaintext_b64_4,
    "protected": JWS_Protected_Header_4_3_2,
    "signature": JWS_Signature_4_3_2}

# 4.4
JWS_Protected_Header_4_4_2 = \
    "eyJhbGciOiJIUzI1NiIsImtpZCI6IjAxOGMwYWU1LTRkOWItNDcxYi1iZmQ2LW" + \
    "VlZjMxNGJjNzAzNyJ9"

JWS_Signature_4_4_2 = "s0h6KThzkfBBBkLspW1h84VsJZFTsPPqMDA7g1Md7p0"

JWS_compact_4_4_3 = \
    "%s.%s.%s" % (JWS_Protected_Header_4_4_2,
                  Payload_plaintext_b64_4,
                  JWS_Signature_4_4_2)

JWS_general_4_4_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "protected": JWS_Protected_Header_4_4_2,
        "signature": JWS_Signature_4_4_2}]}

JWS_flattened_4_4_3 = {
    "payload": Payload_plaintext_b64_4,
    "protected": JWS_Protected_Header_4_4_2,
    "signature": JWS_Signature_4_4_2}

# 4.5 - TBD, see Issue #4

# 4.6
JWS_Protected_Header_4_6_2 = "eyJhbGciOiJIUzI1NiJ9"

JWS_Unprotected_Header_4_6_2 = {"kid": "018c0ae5-4d9b-471b-bfd6-eef314bc7037"}

JWS_Signature_4_6_2 = "bWUSVaxorn7bEF1djytBd0kHv70Ly5pvbomzMWSOr20"

JWS_general_4_6_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "protected": JWS_Protected_Header_4_6_2,
        "header": JWS_Unprotected_Header_4_6_2,
        "signature": JWS_Signature_4_6_2}]}

JWS_flattened_4_6_3 = {
    "payload": Payload_plaintext_b64_4,
    "protected": JWS_Protected_Header_4_6_2,
    "header": JWS_Unprotected_Header_4_6_2,
    "signature": JWS_Signature_4_6_2}

# 4.7
JWS_Unprotected_Header_4_7_2 = {"alg": "HS256",
                                "kid": "018c0ae5-4d9b-471b-bfd6-eef314bc7037"}

JWS_Signature_4_7_2 = "xuLifqLGiblpv9zBpuZczWhNj1gARaLV3UxvxhJxZuk"

JWS_general_4_7_3 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [{
        "header": JWS_Unprotected_Header_4_7_2,
        "signature": JWS_Signature_4_7_2}]}

JWS_flattened_4_7_3 = {
    "payload": Payload_plaintext_b64_4,
    "header": JWS_Unprotected_Header_4_7_2,
    "signature": JWS_Signature_4_7_2}

# 4.8
JWS_Protected_Header_4_8_2 = "eyJhbGciOiJSUzI1NiJ9"

JWS_Unprotected_Header_4_8_2 = {"kid": "bilbo.baggins@hobbiton.example"}

JWS_Signature_4_8_2 = \
    "MIsjqtVlOpa71KE-Mss8_Nq2YH4FGhiocsqrgi5NvyG53uoimic1tcMdSg-qpt" + \
    "rzZc7CG6Svw2Y13TDIqHzTUrL_lR2ZFcryNFiHkSw129EghGpwkpxaTn_THJTC" + \
    "glNbADko1MZBCdwzJxwqZc-1RlpO2HibUYyXSwO97BSe0_evZKdjvvKSgsIqjy" + \
    "tKSeAMbhMBdMma622_BG5t4sdbuCHtFjp9iJmkio47AIwqkZV1aIZsv33uPUqB" + \
    "BCXbYoQJwt7mxPftHmNlGoOSMxR_3thmXTCm4US-xiNOyhbm8afKK64jU6_TPt" + \
    "QHiJeQJxz9G3Tx-083B745_AfYOnlC9w"

JWS_Unprotected_Header_4_8_3 = {"alg": "ES512",
                                "kid": "bilbo.baggins@hobbiton.example"}

JWS_Signature_4_8_3 = \
    "ARcVLnaJJaUWG8fG-8t5BREVAuTY8n8YHjwDO1muhcdCoFZFFjfISu0Cdkn9Yb" + \
    "dlmi54ho0x924DUz8sK7ZXkhc7AFM8ObLfTvNCrqcI3Jkl2U5IX3utNhODH6v7" + \
    "xgy1Qahsn0fyb4zSAkje8bAWz4vIfj5pCMYxxm4fgV3q7ZYhm5eD"

JWS_Protected_Header_4_8_4 = \
    "eyJhbGciOiJIUzI1NiIsImtpZCI6IjAxOGMwYWU1LTRkOWItNDcxYi1iZmQ2LW" + \
    "VlZjMxNGJjNzAzNyJ9"

JWS_Signature_4_8_4 = "s0h6KThzkfBBBkLspW1h84VsJZFTsPPqMDA7g1Md7p0"

JWS_general_4_8_5 = {
    "payload": Payload_plaintext_b64_4,
    "signatures": [
        {"protected": JWS_Protected_Header_4_8_2,
         "header": JWS_Unprotected_Header_4_8_2,
         "signature": JWS_Signature_4_8_2},
        {"header": JWS_Unprotected_Header_4_8_3,
         "signature": JWS_Signature_4_8_3},
        {"protected": JWS_Protected_Header_4_8_4,
         "signature": JWS_Signature_4_8_4}]}


class Cookbook08JWSTests(unittest.TestCase):

    def test_4_1_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        protected = \
            base64url_decode(JWS_Protected_Header_4_1_2).decode('utf-8')
        pub_key = jwk.JWK(**RSA_Public_Key_3_3)
        pri_key = jwk.JWK(**RSA_Private_Key_3_4)
        s = jws.JWS(payload=plaintext)
        s.add_signature(pri_key, None, protected)
        self.assertEqual(JWS_compact_4_1_3, s.serialize(compact=True))
        s.deserialize(json_encode(JWS_general_4_1_3), pub_key)
        s.deserialize(json_encode(JWS_flattened_4_1_3), pub_key)

    def test_4_2_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        protected = \
            base64url_decode(JWS_Protected_Header_4_2_2).decode('utf-8')
        pub_key = jwk.JWK(**RSA_Public_Key_3_3)
        pri_key = jwk.JWK(**RSA_Private_Key_3_4)
        s = jws.JWS(payload=plaintext)
        s.add_signature(pri_key, None, protected)
        # Can't compare signature with reference because RSASSA-PSS uses
        # random nonces every time a signature is generated.
        sig = s.serialize()
        s.deserialize(sig, pub_key)
        # Just deserialize each example form
        s.deserialize(JWS_compact_4_2_3, pub_key)
        s.deserialize(json_encode(JWS_general_4_2_3), pub_key)
        s.deserialize(json_encode(JWS_flattened_4_2_3), pub_key)

    def test_4_3_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        protected = \
            base64url_decode(JWS_Protected_Header_4_3_2).decode('utf-8')
        pub_key = jwk.JWK(**EC_Public_Key_3_1)
        pri_key = jwk.JWK(**EC_Private_Key_3_2)
        s = jws.JWS(payload=plaintext)
        s.add_signature(pri_key, None, protected)
        # Can't compare signature with reference because ECDSA uses
        # random nonces every time a signature is generated.
        sig = s.serialize()
        s.deserialize(sig, pub_key)
        # Just deserialize each example form
        s.deserialize(JWS_compact_4_3_3, pub_key)
        s.deserialize(json_encode(JWS_general_4_3_3), pub_key)
        s.deserialize(json_encode(JWS_flattened_4_3_3), pub_key)

    def test_4_4_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        protected = \
            base64url_decode(JWS_Protected_Header_4_4_2).decode('utf-8')
        key = jwk.JWK(**Symmetric_Key_MAC_3_5)
        s = jws.JWS(payload=plaintext)
        s.add_signature(key, None, protected)
        sig = s.serialize(compact=True)
        s.deserialize(sig, key)
        self.assertEqual(sig, JWS_compact_4_4_3)
        # Just deserialize each example form
        s.deserialize(JWS_compact_4_4_3, key)
        s.deserialize(json_encode(JWS_general_4_4_3), key)
        s.deserialize(json_encode(JWS_flattened_4_4_3), key)

    def test_4_6_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        protected = \
            base64url_decode(JWS_Protected_Header_4_6_2).decode('utf-8')
        header = json_encode(JWS_Unprotected_Header_4_6_2)
        key = jwk.JWK(**Symmetric_Key_MAC_3_5)
        s = jws.JWS(payload=plaintext)
        s.add_signature(key, None, protected, header)
        sig = s.serialize()
        s.deserialize(sig, key)
        self.assertEqual(json_decode(sig), JWS_flattened_4_6_3)
        # Just deserialize each example form
        s.deserialize(json_encode(JWS_general_4_6_3), key)
        s.deserialize(json_encode(JWS_flattened_4_6_3), key)

    def test_4_7_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        header = json_encode(JWS_Unprotected_Header_4_7_2)
        key = jwk.JWK(**Symmetric_Key_MAC_3_5)
        s = jws.JWS(payload=plaintext)
        s.add_signature(key, None, None, header)
        sig = s.serialize()
        s.deserialize(sig, key)
        self.assertEqual(json_decode(sig), JWS_flattened_4_7_3)
        # Just deserialize each example form
        s.deserialize(json_encode(JWS_general_4_7_3), key)
        s.deserialize(json_encode(JWS_flattened_4_7_3), key)

    def test_4_8_signing(self):
        plaintext = base64url_decode(Payload_plaintext_b64_4)
        s = jws.JWS(payload=plaintext)
        # 4_8_2
        protected = \
            base64url_decode(JWS_Protected_Header_4_8_2).decode('utf-8')
        header = json_encode(JWS_Unprotected_Header_4_8_2)
        pri_key = jwk.JWK(**RSA_Private_Key_3_4)
        s.add_signature(pri_key, None, protected, header)
        # 4_8_3
        header = json_encode(JWS_Unprotected_Header_4_8_3)
        pri_key = jwk.JWK(**EC_Private_Key_3_2)
        s.add_signature(pri_key, None, None, header)
        # 4_8_4
        protected = \
            base64url_decode(JWS_Protected_Header_4_8_4).decode('utf-8')
        sym_key = jwk.JWK(**Symmetric_Key_MAC_3_5)
        s.add_signature(sym_key, None, protected)
        sig = s.serialize()
        # Can't compare signature with reference because ECDSA uses
        # random nonces every time a signature is generated.
        rsa_key = jwk.JWK(**RSA_Public_Key_3_3)
        ec_key = jwk.JWK(**EC_Public_Key_3_1)
        s.deserialize(sig, rsa_key)
        s.deserialize(sig, ec_key)
        s.deserialize(sig, sym_key)
        # Just deserialize each example form
        s.deserialize(json_encode(JWS_general_4_8_5), rsa_key)
        s.deserialize(json_encode(JWS_general_4_8_5), ec_key)
        s.deserialize(json_encode(JWS_general_4_8_5), sym_key)


# 5.0
Payload_plaintext_5 = \
    b"You can trust us to stick with you through thick and " + \
    b"thin\xe2\x80\x93to the bitter end. And you can trust us to " + \
    b"keep any secret of yours\xe2\x80\x93closer than you keep it " + \
    b"yourself. But you cannot trust us to let you face trouble " + \
    b"alone, and go off without a word. We are your friends, Frodo."

# 5.1
RSA_key_5_1_1 = {
    "kty": "RSA",
    "kid": "frodo.baggins@hobbiton.example",
    "use": "enc",
    "n": "maxhbsmBtdQ3CNrKvprUE6n9lYcregDMLYNeTAWcLj8NnPU9XIYegT"
         "HVHQjxKDSHP2l-F5jS7sppG1wgdAqZyhnWvXhYNvcM7RfgKxqNx_xAHx"
         "6f3yy7s-M9PSNCwPC2lh6UAkR4I00EhV9lrypM9Pi4lBUop9t5fS9W5U"
         "NwaAllhrd-osQGPjIeI1deHTwx-ZTHu3C60Pu_LJIl6hKn9wbwaUmA4c"
         "R5Bd2pgbaY7ASgsjCUbtYJaNIHSoHXprUdJZKUMAzV0WOKPfA6OPI4oy"
         "pBadjvMZ4ZAj3BnXaSYsEZhaueTXvZB4eZOAjIyh2e_VOIKVMsnDrJYA"
         "VotGlvMQ",
    "e": "AQAB",
    "d": "Kn9tgoHfiTVi8uPu5b9TnwyHwG5dK6RE0uFdlpCGnJN7ZEi963R7wy"
         "bQ1PLAHmpIbNTztfrheoAniRV1NCIqXaW_qS461xiDTp4ntEPnqcKsyO"
         "5jMAji7-CL8vhpYYowNFvIesgMoVaPRYMYT9TW63hNM0aWs7USZ_hLg6"
         "Oe1mY0vHTI3FucjSM86Nff4oIENt43r2fspgEPGRrdE6fpLc9Oaq-qeP"
         "1GFULimrRdndm-P8q8kvN3KHlNAtEgrQAgTTgz80S-3VD0FgWfgnb1PN"
         "miuPUxO8OpI9KDIfu_acc6fg14nsNaJqXe6RESvhGPH2afjHqSy_Fd2v"
         "pzj85bQQ",
    "p": "2DwQmZ43FoTnQ8IkUj3BmKRf5Eh2mizZA5xEJ2MinUE3sdTYKSLtaE"
         "oekX9vbBZuWxHdVhM6UnKCJ_2iNk8Z0ayLYHL0_G21aXf9-unynEpUsH"
         "7HHTklLpYAzOOx1ZgVljoxAdWNn3hiEFrjZLZGS7lOH-a3QQlDDQoJOJ"
         "2VFmU",
    "q": "te8LY4-W7IyaqH1ExujjMqkTAlTeRbv0VLQnfLY2xINnrWdwiQ93_V"
         "F099aP1ESeLja2nw-6iKIe-qT7mtCPozKfVtUYfz5HrJ_XY2kfexJINb"
         "9lhZHMv5p1skZpeIS-GPHCC6gRlKo1q-idn_qxyusfWv7WAxlSVfQfk8"
         "d6Et0",
    "dp": "UfYKcL_or492vVc0PzwLSplbg4L3-Z5wL48mwiswbpzOyIgd2xHTH"
          "QmjJpFAIZ8q-zf9RmgJXkDrFs9rkdxPtAsL1WYdeCT5c125Fkdg317JV"
          "RDo1inX7x2Kdh8ERCreW8_4zXItuTl_KiXZNU5lvMQjWbIw2eTx1lpsf"
          "lo0rYU",
    "dq": "iEgcO-QfpepdH8FWd7mUFyrXdnOkXJBCogChY6YKuIHGc_p8Le9Mb"
          "pFKESzEaLlN1Ehf3B6oGBl5Iz_ayUlZj2IoQZ82znoUrpa9fVYNot87A"
          "CfzIG7q9Mv7RiPAderZi03tkVXAdaBau_9vs5rS-7HMtxkVrxSUvJY14"
          "TkXlHE",
    "qi": "kC-lzZOqoFaZCr5l0tOVtREKoVqaAYhQiqIRGL-MzS4sCmRkxm5vZ"
          "lXYx6RtE1n_AagjqajlkjieGlxTTThHD8Iga6foGBMaAr5uR1hGQpSc7"
          "Gl7CF1DZkBJMTQN6EshYzZfxW08mIO8M6Rzuh0beL6fG9mkDcIyPrBXx"
          "2bQ_mM"}

JWE_IV_5_1_2 = "bbd5sTkYwhAIqfHsx8DayA"

JWE_Encrypted_Key_5_1_3 = \
    "laLxI0j-nLH-_BgLOXMozKxmy9gffy2gTdvqzfTihJBuuzxg0V7yk1WClnQePF" + \
    "vG2K-pvSlWc9BRIazDrn50RcRai__3TDON395H3c62tIouJJ4XaRvYHFjZTZ2G" + \
    "Xfz8YAImcc91Tfk0WXC2F5Xbb71ClQ1DDH151tlpH77f2ff7xiSxh9oSewYrcG" + \
    "TSLUeeCt36r1Kt3OSj7EyBQXoZlN7IxbyhMAfgIe7Mv1rOTOI5I8NQqeXXW8Vl" + \
    "zNmoxaGMny3YnGir5Wf6Qt2nBq4qDaPdnaAuuGUGEecelIO1wx1BpyIfgvfjOh" + \
    "MBs9M8XL223Fg47xlGsMXdfuY-4jaqVw"

JWE_Protected_Header_5_1_4 = \
    "eyJhbGciOiJSU0ExXzUiLCJraWQiOiJmcm9kby5iYWdnaW5zQGhvYmJpdG9uLm" + \
    "V4YW1wbGUiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0"

JWE_Ciphertext_5_1_4 = \
    "0fys_TY_na7f8dwSfXLiYdHaA2DxUjD67ieF7fcVbIR62JhJvGZ4_FNVSiGc_r" + \
    "aa0HnLQ6s1P2sv3Xzl1p1l_o5wR_RsSzrS8Z-wnI3Jvo0mkpEEnlDmZvDu_k8O" + \
    "WzJv7eZVEqiWKdyVzFhPpiyQU28GLOpRc2VbVbK4dQKPdNTjPPEmRqcaGeTWZV" + \
    "yeSUvf5k59yJZxRuSvWFf6KrNtmRdZ8R4mDOjHSrM_s8uwIFcqt4r5GX8TKaI0" + \
    "zT5CbL5Qlw3sRc7u_hg0yKVOiRytEAEs3vZkcfLkP6nbXdC_PkMdNS-ohP78T2" + \
    "O6_7uInMGhFeX4ctHG7VelHGiT93JfWDEQi5_V9UN1rhXNrYu-0fVMkZAKX3VW" + \
    "i7lzA6BP430m"

JWE_Authentication_Tag_5_1_4 = "kvKuFBXHe5mQr4lqgobAUg"

JWE_compact_5_1_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_1_4,
                        JWE_Encrypted_Key_5_1_3,
                        JWE_IV_5_1_2,
                        JWE_Ciphertext_5_1_4,
                        JWE_Authentication_Tag_5_1_4)

JWE_general_5_1_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_1_3}],
    "protected": JWE_Protected_Header_5_1_4,
    "iv": JWE_IV_5_1_2,
    "ciphertext": JWE_Ciphertext_5_1_4,
    "tag": JWE_Authentication_Tag_5_1_4}

JWE_flattened_5_1_5 = {
    "protected": JWE_Protected_Header_5_1_4,
    "encrypted_key": JWE_Encrypted_Key_5_1_3,
    "iv": JWE_IV_5_1_2,
    "ciphertext": JWE_Ciphertext_5_1_4,
    "tag": JWE_Authentication_Tag_5_1_4}

# 5.2
RSA_key_5_2_1 = {
    "kty": "RSA",
    "kid": "samwise.gamgee@hobbiton.example",
    "use": "enc",
    "n": "wbdxI55VaanZXPY29Lg5hdmv2XhvqAhoxUkanfzf2-5zVUxa6prHRr"
         "I4pP1AhoqJRlZfYtWWd5mmHRG2pAHIlh0ySJ9wi0BioZBl1XP2e-C-Fy"
         "XJGcTy0HdKQWlrfhTm42EW7Vv04r4gfao6uxjLGwfpGrZLarohiWCPnk"
         "Nrg71S2CuNZSQBIPGjXfkmIy2tl_VWgGnL22GplyXj5YlBLdxXp3XeSt"
         "sqo571utNfoUTU8E4qdzJ3U1DItoVkPGsMwlmmnJiwA7sXRItBCivR4M"
         "5qnZtdw-7v4WuR4779ubDuJ5nalMv2S66-RPcnFAzWSKxtBDnFJJDGIU"
         "e7Tzizjg1nms0Xq_yPub_UOlWn0ec85FCft1hACpWG8schrOBeNqHBOD"
         "FskYpUc2LC5JA2TaPF2dA67dg1TTsC_FupfQ2kNGcE1LgprxKHcVWYQb"
         "86B-HozjHZcqtauBzFNV5tbTuB-TpkcvJfNcFLlH3b8mb-H_ox35FjqB"
         "SAjLKyoeqfKTpVjvXhd09knwgJf6VKq6UC418_TOljMVfFTWXUxlnfhO"
         "OnzW6HSSzD1c9WrCuVzsUMv54szidQ9wf1cYWf3g5qFDxDQKis99gcDa"
         "iCAwM3yEBIzuNeeCa5dartHDb1xEB_HcHSeYbghbMjGfasvKn0aZRsnT"
         "yC0xhWBlsolZE",
    "e": "AQAB",
    "alg": "RSA-OAEP",
    "d": "n7fzJc3_WG59VEOBTkayzuSMM780OJQuZjN_KbH8lOZG25ZoA7T4Bx"
         "cc0xQn5oZE5uSCIwg91oCt0JvxPcpmqzaJZg1nirjcWZ-oBtVk7gCAWq"
         "-B3qhfF3izlbkosrzjHajIcY33HBhsy4_WerrXg4MDNE4HYojy68TcxT"
         "2LYQRxUOCf5TtJXvM8olexlSGtVnQnDRutxEUCwiewfmmrfveEogLx9E"
         "A-KMgAjTiISXxqIXQhWUQX1G7v_mV_Hr2YuImYcNcHkRvp9E7ook0876"
         "DhkO8v4UOZLwA1OlUX98mkoqwc58A_Y2lBYbVx1_s5lpPsEqbbH-nqIj"
         "h1fL0gdNfihLxnclWtW7pCztLnImZAyeCWAG7ZIfv-Rn9fLIv9jZ6r7r"
         "-MSH9sqbuziHN2grGjD_jfRluMHa0l84fFKl6bcqN1JWxPVhzNZo01yD"
         "F-1LiQnqUYSepPf6X3a2SOdkqBRiquE6EvLuSYIDpJq3jDIsgoL8Mo1L"
         "oomgiJxUwL_GWEOGu28gplyzm-9Q0U0nyhEf1uhSR8aJAQWAiFImWH5W"
         "_IQT9I7-yrindr_2fWQ_i1UgMsGzA7aOGzZfPljRy6z-tY_KuBG00-28"
         "S_aWvjyUc-Alp8AUyKjBZ-7CWH32fGWK48j1t-zomrwjL_mnhsPbGs0c"
         "9WsWgRzI-K8gE",
    "p": "7_2v3OQZzlPFcHyYfLABQ3XP85Es4hCdwCkbDeltaUXgVy9l9etKgh"
         "vM4hRkOvbb01kYVuLFmxIkCDtpi-zLCYAdXKrAK3PtSbtzld_XZ9nlsY"
         "a_QZWpXB_IrtFjVfdKUdMz94pHUhFGFj7nr6NNxfpiHSHWFE1zD_AC3m"
         "Y46J961Y2LRnreVwAGNw53p07Db8yD_92pDa97vqcZOdgtybH9q6uma-"
         "RFNhO1AoiJhYZj69hjmMRXx-x56HO9cnXNbmzNSCFCKnQmn4GQLmRj9s"
         "fbZRqL94bbtE4_e0Zrpo8RNo8vxRLqQNwIy85fc6BRgBJomt8QdQvIgP"
         "gWCv5HoQ",
    "q": "zqOHk1P6WN_rHuM7ZF1cXH0x6RuOHq67WuHiSknqQeefGBA9PWs6Zy"
         "KQCO-O6mKXtcgE8_Q_hA2kMRcKOcvHil1hqMCNSXlflM7WPRPZu2qCDc"
         "qssd_uMbP-DqYthH_EzwL9KnYoH7JQFxxmcv5An8oXUtTwk4knKjkIYG"
         "RuUwfQTus0w1NfjFAyxOOiAQ37ussIcE6C6ZSsM3n41UlbJ7TCqewzVJ"
         "aPJN5cxjySPZPD3Vp01a9YgAD6a3IIaKJdIxJS1ImnfPevSJQBE79-EX"
         "e2kSwVgOzvt-gsmM29QQ8veHy4uAqca5dZzMs7hkkHtw1z0jHV90epQJ"
         "JlXXnH8Q",
    "dp": "19oDkBh1AXelMIxQFm2zZTqUhAzCIr4xNIGEPNoDt1jK83_FJA-xn"
          "x5kA7-1erdHdms_Ef67HsONNv5A60JaR7w8LHnDiBGnjdaUmmuO8XAxQ"
          "J_ia5mxjxNjS6E2yD44USo2JmHvzeeNczq25elqbTPLhUpGo1IZuG72F"
          "ZQ5gTjXoTXC2-xtCDEUZfaUNh4IeAipfLugbpe0JAFlFfrTDAMUFpC3i"
          "XjxqzbEanflwPvj6V9iDSgjj8SozSM0dLtxvu0LIeIQAeEgT_yXcrKGm"
          "pKdSO08kLBx8VUjkbv_3Pn20Gyu2YEuwpFlM_H1NikuxJNKFGmnAq9Lc"
          "nwwT0jvoQ",
    "dq": "S6p59KrlmzGzaQYQM3o0XfHCGvfqHLYjCO557HYQf72O9kLMCfd_1"
          "VBEqeD-1jjwELKDjck8kOBl5UvohK1oDfSP1DleAy-cnmL29DqWmhgwM"
          "1ip0CCNmkmsmDSlqkUXDi6sAaZuntyukyflI-qSQ3C_BafPyFaKrt1fg"
          "dyEwYa08pESKwwWisy7KnmoUvaJ3SaHmohFS78TJ25cfc10wZ9hQNOrI"
          "ChZlkiOdFCtxDqdmCqNacnhgE3bZQjGp3n83ODSz9zwJcSUvODlXBPc2"
          "AycH6Ci5yjbxt4Ppox_5pjm6xnQkiPgj01GpsUssMmBN7iHVsrE7N2iz"
          "nBNCeOUIQ",
    "qi": "FZhClBMywVVjnuUud-05qd5CYU0dK79akAgy9oX6RX6I3IIIPckCc"
          "iRrokxglZn-omAY5CnCe4KdrnjFOT5YUZE7G_Pg44XgCXaarLQf4hl80"
          "oPEf6-jJ5Iy6wPRx7G2e8qLxnh9cOdf-kRqgOS3F48Ucvw3ma5V6KGMw"
          "QqWFeV31XtZ8l5cVI-I3NzBS7qltpUVgz2Ju021eyc7IlqgzR98qKONl"
          "27DuEES0aK0WE97jnsyO27Yp88Wa2RiBrEocM89QZI1seJiGDizHRUP4"
          "UZxw9zsXww46wy0P6f9grnYp7t8LkyDDk8eoI4KX6SNMNVcyVS9IWjlq"
          "8EzqZEKIA"}

JWE_IV_5_2_2 = "-nBoKLH0YkLZPSI9"

JWE_Encrypted_Key_5_2_3 = \
    "rT99rwrBTbTI7IJM8fU3Eli7226HEB7IchCxNuh7lCiud48LxeolRdtFF4nzQi" + \
    "beYOl5S_PJsAXZwSXtDePz9hk-BbtsTBqC2UsPOdwjC9NhNupNNu9uHIVftDyu" + \
    "cvI6hvALeZ6OGnhNV4v1zx2k7O1D89mAzfw-_kT3tkuorpDU-CpBENfIHX1Q58" + \
    "-Aad3FzMuo3Fn9buEP2yXakLXYa15BUXQsupM4A1GD4_H4Bd7V3u9h8Gkg8Bpx" + \
    "KdUV9ScfJQTcYm6eJEBz3aSwIaK4T3-dwWpuBOhROQXBosJzS1asnuHtVMt2pK" + \
    "IIfux5BC6huIvmY7kzV7W7aIUrpYm_3H4zYvyMeq5pGqFmW2k8zpO878TRlZx7" + \
    "pZfPYDSXZyS0CfKKkMozT_qiCwZTSz4duYnt8hS4Z9sGthXn9uDqd6wycMagnQ" + \
    "fOTs_lycTWmY-aqWVDKhjYNRf03NiwRtb5BE-tOdFwCASQj3uuAgPGrO2AWBe3" + \
    "8UjQb0lvXn1SpyvYZ3WFc7WOJYaTa7A8DRn6MC6T-xDmMuxC0G7S2rscw5lQQU" + \
    "06MvZTlFOt0UvfuKBa03cxA_nIBIhLMjY2kOTxQMmpDPTr6Cbo8aKaOnx6ASE5" + \
    "Jx9paBpnNmOOKH35j_QlrQhDWUN6A2Gg8iFayJ69xDEdHAVCGRzN3woEI2ozDR" + \
    "s"

JWE_Protected_Header_5_2_4 = \
    "eyJhbGciOiJSU0EtT0FFUCIsImtpZCI6InNhbXdpc2UuZ2FtZ2VlQGhvYmJpdG" + \
    "9uLmV4YW1wbGUiLCJlbmMiOiJBMjU2R0NNIn0"

JWE_Ciphertext_5_2_4 = \
    "o4k2cnGN8rSSw3IDo1YuySkqeS_t2m1GXklSgqBdpACm6UJuJowOHC5ytjqYgR" + \
    "L-I-soPlwqMUf4UgRWWeaOGNw6vGW-xyM01lTYxrXfVzIIaRdhYtEMRBvBWbEw" + \
    "P7ua1DRfvaOjgZv6Ifa3brcAM64d8p5lhhNcizPersuhw5f-pGYzseva-TUaL8" + \
    "iWnctc-sSwy7SQmRkfhDjwbz0fz6kFovEgj64X1I5s7E6GLp5fnbYGLa1QUiML" + \
    "7Cc2GxgvI7zqWo0YIEc7aCflLG1-8BboVWFdZKLK9vNoycrYHumwzKluLWEbSV" + \
    "maPpOslY2n525DxDfWaVFUfKQxMF56vn4B9QMpWAbnypNimbM8zVOw"

JWE_Authentication_Tag_5_2_4 = "UCGiqJxhBI3IFVdPalHHvA"

JWE_compact_5_2_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_2_4,
                        JWE_Encrypted_Key_5_2_3,
                        JWE_IV_5_2_2,
                        JWE_Ciphertext_5_2_4,
                        JWE_Authentication_Tag_5_2_4)

JWE_general_5_2_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_2_3}],
    "protected": JWE_Protected_Header_5_2_4,
    "iv": JWE_IV_5_2_2,
    "ciphertext": JWE_Ciphertext_5_2_4,
    "tag": JWE_Authentication_Tag_5_2_4}

JWE_flattened_5_2_5 = {
    "protected": JWE_Protected_Header_5_2_4,
    "encrypted_key": JWE_Encrypted_Key_5_2_3,
    "iv": JWE_IV_5_2_2,
    "ciphertext": JWE_Ciphertext_5_2_4,
    "tag": JWE_Authentication_Tag_5_2_4}

# 5.3
Payload_plaintext_5_3_1 = \
    b'{"keys":[{"kty":"oct","kid":"77c7e2b8-6e13-45cf-8672-617b5b45' + \
    b'243a","use":"enc","alg":"A128GCM","k":"XctOhJAkA-pD9Lh7ZgW_2A' + \
    b'"},{"kty":"oct","kid":"81b20965-8332-43d9-a468-82160ad91ac8",' + \
    b'"use":"enc","alg":"A128KW","k":"GZy6sIZ6wl9NJOKB-jnmVQ"},{"kt' + \
    b'y":"oct","kid":"18ec08e1-bfa9-4d95-b205-2b4dd1d4321d","use":"' + \
    b'enc","alg":"A256GCMKW","k":"qC57l_uxcm7Nm3K-ct4GFjx8tM1U8CZ0N' + \
    b'LBvdQstiS8"}]}'

Password_5_3_1 = b'entrap_o\xe2\x80\x93peter_long\xe2\x80\x93credit_tun'

JWE_IV_5_3_2 = "VBiCzVHNoLiR3F4V82uoTQ"

JWE_Encrypted_Key_5_3_3 = \
    "d3qNhUWfqheyPp4H8sjOWsDYajoej4c5Je6rlUtFPWdgtURtmeDV1g"

JWE_Protected_Header_no_p2x = {
    "alg": "PBES2-HS512+A256KW",
    "cty": "jwk-set+json",
    "enc": "A128CBC-HS256"}

JWE_Protected_Header_5_3_4 = \
    "eyJhbGciOiJQQkVTMi1IUzUxMitBMjU2S1ciLCJwMnMiOiI4UTFTemluYXNSM3" + \
    "hjaFl6NlpaY0hBIiwicDJjIjo4MTkyLCJjdHkiOiJqd2stc2V0K2pzb24iLCJl" + \
    "bmMiOiJBMTI4Q0JDLUhTMjU2In0"

JWE_Ciphertext_5_3_4 = \
    "23i-Tb1AV4n0WKVSSgcQrdg6GRqsUKxjruHXYsTHAJLZ2nsnGIX86vMXqIi6IR" + \
    "sfywCRFzLxEcZBRnTvG3nhzPk0GDD7FMyXhUHpDjEYCNA_XOmzg8yZR9oyjo6l" + \
    "TF6si4q9FZ2EhzgFQCLO_6h5EVg3vR75_hkBsnuoqoM3dwejXBtIodN84PeqMb" + \
    "6asmas_dpSsz7H10fC5ni9xIz424givB1YLldF6exVmL93R3fOoOJbmk2GBQZL" + \
    "_SEGllv2cQsBgeprARsaQ7Bq99tT80coH8ItBjgV08AtzXFFsx9qKvC982KLKd" + \
    "PQMTlVJKkqtV4Ru5LEVpBZXBnZrtViSOgyg6AiuwaS-rCrcD_ePOGSuxvgtrok" + \
    "AKYPqmXUeRdjFJwafkYEkiuDCV9vWGAi1DH2xTafhJwcmywIyzi4BqRpmdn_N-" + \
    "zl5tuJYyuvKhjKv6ihbsV_k1hJGPGAxJ6wUpmwC4PTQ2izEm0TuSE8oMKdTw8V" + \
    "3kobXZ77ulMwDs4p"

JWE_Authentication_Tag_5_3_4 = "0HlwodAhOCILG5SQ2LQ9dg"

JWE_compact_5_3_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_3_4,
                        JWE_Encrypted_Key_5_3_3,
                        JWE_IV_5_3_2,
                        JWE_Ciphertext_5_3_4,
                        JWE_Authentication_Tag_5_3_4)

JWE_general_5_3_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_3_3}],
    "protected": JWE_Protected_Header_5_3_4,
    "iv": JWE_IV_5_3_2,
    "ciphertext": JWE_Ciphertext_5_3_4,
    "tag": JWE_Authentication_Tag_5_3_4}

JWE_flattened_5_3_5 = {
    "protected": JWE_Protected_Header_5_3_4,
    "encrypted_key": JWE_Encrypted_Key_5_3_3,
    "iv": JWE_IV_5_3_2,
    "ciphertext": JWE_Ciphertext_5_3_4,
    "tag": JWE_Authentication_Tag_5_3_4}

# 5.4
EC_key_5_4_1 = {
    "kty": "EC",
    "kid": "peregrin.took@tuckborough.example",
    "use": "enc",
    "crv": "P-384",
    "x": "YU4rRUzdmVqmRtWOs2OpDE_T5fsNIodcG8G5FWPrTPMyxpzsSOGaQLpe2FpxBmu2",
    "y": "A8-yxCHxkfBz3hKZfI1jUYMjUhsEveZ9THuwFjH2sCNdtksRJU7D5-SkgaFL1ETP",
    "d": "iTx2pk7wW-GqJkHcEkFQb2EFyYcO7RugmaW3mRrQVAOUiPommT0IdnYK2xDlZh-j"}

JWE_IV_5_4_2 = "mH-G2zVqgztUtnW_"

JWE_Encrypted_Key_5_4_3 = \
    "0DJjBXri_kBcC46IkU5_Jk9BqaQeHdv2"

JWE_Protected_Header_no_epk_5_4_4 = {
    "alg": "ECDH-ES+A128KW",
    "kid": "peregrin.took@tuckborough.example",
    "enc": "A128GCM"}

JWE_Protected_Header_5_4_4 = \
    "eyJhbGciOiJFQ0RILUVTK0ExMjhLVyIsImtpZCI6InBlcmVncmluLnRvb2tAdH" + \
    "Vja2Jvcm91Z2guZXhhbXBsZSIsImVwayI6eyJrdHkiOiJFQyIsImNydiI6IlAt" + \
    "Mzg0IiwieCI6InVCbzRrSFB3Nmtiang1bDB4b3dyZF9vWXpCbWF6LUdLRlp1NH" + \
    "hBRkZrYllpV2d1dEVLNml1RURzUTZ3TmROZzMiLCJ5Ijoic3AzcDVTR2haVkMy" + \
    "ZmFYdW1JLWU5SlUyTW84S3BvWXJGRHI1eVBOVnRXNFBnRXdaT3lRVEEtSmRhWT" + \
    "h0YjdFMCJ9LCJlbmMiOiJBMTI4R0NNIn0"

JWE_Ciphertext_5_4_4 = \
    "tkZuOO9h95OgHJmkkrfLBisku8rGf6nzVxhRM3sVOhXgz5NJ76oID7lpnAi_cP" + \
    "WJRCjSpAaUZ5dOR3Spy7QuEkmKx8-3RCMhSYMzsXaEwDdXta9Mn5B7cCBoJKB0" + \
    "IgEnj_qfo1hIi-uEkUpOZ8aLTZGHfpl05jMwbKkTe2yK3mjF6SBAsgicQDVCkc" + \
    "Y9BLluzx1RmC3ORXaM0JaHPB93YcdSDGgpgBWMVrNU1ErkjcMqMoT_wtCex3w0" + \
    "3XdLkjXIuEr2hWgeP-nkUZTPU9EoGSPj6fAS-bSz87RCPrxZdj_iVyC6QWcqAu" + \
    "07WNhjzJEPc4jVntRJ6K53NgPQ5p99l3Z408OUqj4ioYezbS6vTPlQ"

JWE_Authentication_Tag_5_4_4 = "WuGzxmcreYjpHGJoa17EBg"

JWE_compact_5_4_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_4_4,
                        JWE_Encrypted_Key_5_4_3,
                        JWE_IV_5_4_2,
                        JWE_Ciphertext_5_4_4,
                        JWE_Authentication_Tag_5_4_4)

JWE_general_5_4_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_4_3}],
    "protected": JWE_Protected_Header_5_4_4,
    "iv": JWE_IV_5_4_2,
    "ciphertext": JWE_Ciphertext_5_4_4,
    "tag": JWE_Authentication_Tag_5_4_4}

JWE_flattened_5_4_5 = {
    "protected": JWE_Protected_Header_5_4_4,
    "encrypted_key": JWE_Encrypted_Key_5_4_3,
    "iv": JWE_IV_5_4_2,
    "ciphertext": JWE_Ciphertext_5_4_4,
    "tag": JWE_Authentication_Tag_5_4_4}

# 5.5
EC_key_5_5_1 = {
    "kty": "EC",
    "kid": "meriadoc.brandybuck@buckland.example",
    "use": "enc",
    "crv": "P-256",
    "x": "Ze2loSV3wrroKUN_4zhwGhCqo3Xhu1td4QjeQ5wIVR0",
    "y": "HlLtdXARY_f55A3fnzQbPcm6hgr34Mp8p-nuzQCE0Zw",
    "d": "r_kHyZ-a06rmxM3yESK84r1otSg-aQcVStkRhA-iCM8"}

JWE_IV_5_5_2 = "yc9N8v5sYyv3iGQT926IUg"

JWE_Protected_Header_no_epk_5_5_4 = {
    "alg": "ECDH-ES",
    "kid": "meriadoc.brandybuck@buckland.example",
    "enc": "A128CBC-HS256"
}

JWE_Protected_Header_5_5_4 = \
    "eyJhbGciOiJFQ0RILUVTIiwia2lkIjoibWVyaWFkb2MuYnJhbmR5YnVja0BidW" + \
    "NrbGFuZC5leGFtcGxlIiwiZXBrIjp7Imt0eSI6IkVDIiwiY3J2IjoiUC0yNTYi" + \
    "LCJ4IjoibVBVS1RfYkFXR0hJaGcwVHBqanFWc1AxclhXUXVfdndWT0hIdE5rZF" + \
    "lvQSIsInkiOiI4QlFBc0ltR2VBUzQ2ZnlXdzVNaFlmR1RUMElqQnBGdzJTUzM0" + \
    "RHY0SXJzIn0sImVuYyI6IkExMjhDQkMtSFMyNTYifQ"

JWE_Ciphertext_5_5_4 = \
    "BoDlwPnTypYq-ivjmQvAYJLb5Q6l-F3LIgQomlz87yW4OPKbWE1zSTEFjDfhU9" + \
    "IPIOSA9Bml4m7iDFwA-1ZXvHteLDtw4R1XRGMEsDIqAYtskTTmzmzNa-_q4F_e" + \
    "vAPUmwlO-ZG45Mnq4uhM1fm_D9rBtWolqZSF3xGNNkpOMQKF1Cl8i8wjzRli7-" + \
    "IXgyirlKQsbhhqRzkv8IcY6aHl24j03C-AR2le1r7URUhArM79BY8soZU0lzwI" + \
    "-sD5PZ3l4NDCCei9XkoIAfsXJWmySPoeRb2Ni5UZL4mYpvKDiwmyzGd65KqVw7" + \
    "MsFfI_K767G9C9Azp73gKZD0DyUn1mn0WW5LmyX_yJ-3AROq8p1WZBfG-ZyJ61" + \
    "95_JGG2m9Csg"

JWE_Authentication_Tag_5_5_4 = "WCCkNa-x4BeB9hIDIfFuhg"

JWE_compact_5_5_5 = \
    "%s..%s.%s.%s" % (JWE_Protected_Header_5_5_4,
                      JWE_IV_5_5_2,
                      JWE_Ciphertext_5_5_4,
                      JWE_Authentication_Tag_5_5_4)

JWE_general_5_5_5 = {
    "protected": JWE_Protected_Header_5_5_4,
    "iv": JWE_IV_5_5_2,
    "ciphertext": JWE_Ciphertext_5_5_4,
    "tag": JWE_Authentication_Tag_5_5_4}

# 5.6
AES_key_5_6_1 = {
    "kty": "oct",
    "kid": "77c7e2b8-6e13-45cf-8672-617b5b45243a",
    "use": "enc",
    "alg": "A128GCM",
    "k": "XctOhJAkA-pD9Lh7ZgW_2A"}

JWE_IV_5_6_2 = "refa467QzzKx6QAB"

JWE_Protected_Header_5_6_3 = \
    "eyJhbGciOiJkaXIiLCJraWQiOiI3N2M3ZTJiOC02ZTEzLTQ1Y2YtODY3Mi02MT" + \
    "diNWI0NTI0M2EiLCJlbmMiOiJBMTI4R0NNIn0"

JWE_Ciphertext_5_6_3 = \
    "JW_i_f52hww_ELQPGaYyeAB6HYGcR559l9TYnSovc23XJoBcW29rHP8yZOZG7Y" + \
    "hLpT1bjFuvZPjQS-m0IFtVcXkZXdH_lr_FrdYt9HRUYkshtrMmIUAyGmUnd9zM" + \
    "DB2n0cRDIHAzFVeJUDxkUwVAE7_YGRPdcqMyiBoCO-FBdE-Nceb4h3-FtBP-c_" + \
    "BIwCPTjb9o0SbdcdREEMJMyZBH8ySWMVi1gPD9yxi-aQpGbSv_F9N4IZAxscj5" + \
    "g-NJsUPbjk29-s7LJAGb15wEBtXphVCgyy53CoIKLHHeJHXex45Uz9aKZSRSIn" + \
    "ZI-wjsY0yu3cT4_aQ3i1o-tiE-F8Ios61EKgyIQ4CWao8PFMj8TTnp"

JWE_Authentication_Tag_5_6_3 = "vbb32Xvllea2OtmHAdccRQ"

JWE_compact_5_6_4 = \
    "%s..%s.%s.%s" % (JWE_Protected_Header_5_6_3,
                      JWE_IV_5_6_2,
                      JWE_Ciphertext_5_6_3,
                      JWE_Authentication_Tag_5_6_3)

JWE_general_5_6_4 = {
    "protected": JWE_Protected_Header_5_6_3,
    "iv": JWE_IV_5_6_2,
    "ciphertext": JWE_Ciphertext_5_6_3,
    "tag": JWE_Authentication_Tag_5_6_3}

# 5.7 - A256GCMKW not implemented yet
AES_key_5_7_1 = {
    "kty": "oct",
    "kid": "18ec08e1-bfa9-4d95-b205-2b4dd1d4321d",
    "use": "enc",
    "alg": "A256GCMKW",
    "k": "qC57l_uxcm7Nm3K-ct4GFjx8tM1U8CZ0NLBvdQstiS8"}

JWE_IV_5_7_2 = "gz6NjyEFNm_vm8Gj6FwoFQ"

JWE_Encrypted_Key_5_7_3 = "lJf3HbOApxMEBkCMOoTnnABxs_CvTWUmZQ2ElLvYNok"

JWE_Protected_Header_no_ivtag = {
    "alg": "A256GCMKW",
    "kid": "18ec08e1-bfa9-4d95-b205-2b4dd1d4321d",
    "enc": "A128CBC-HS256"}

JWE_Protected_Header_5_7_4 = \
    "eyJhbGciOiJBMjU2R0NNS1ciLCJraWQiOiIxOGVjMDhlMS1iZmE5LTRkOTUtYj" + \
    "IwNS0yYjRkZDFkNDMyMWQiLCJ0YWciOiJrZlBkdVZRM1QzSDZ2bmV3dC0ta3N3" + \
    "IiwiaXYiOiJLa1lUMEdYXzJqSGxmcU5fIiwiZW5jIjoiQTEyOENCQy1IUzI1Ni" + \
    "J9"

JWE_Ciphertext_5_7_4 = \
    "Jf5p9-ZhJlJy_IQ_byKFmI0Ro7w7G1QiaZpI8OaiVgD8EqoDZHyFKFBupS8iaE" + \
    "eVIgMqWmsuJKuoVgzR3YfzoMd3GxEm3VxNhzWyWtZKX0gxKdy6HgLvqoGNbZCz" + \
    "LjqcpDiF8q2_62EVAbr2uSc2oaxFmFuIQHLcqAHxy51449xkjZ7ewzZaGV3eFq" + \
    "hpco8o4DijXaG5_7kp3h2cajRfDgymuxUbWgLqaeNQaJtvJmSMFuEOSAzw9Hde" + \
    "b6yhdTynCRmu-kqtO5Dec4lT2OMZKpnxc_F1_4yDJFcqb5CiDSmA-psB2k0Jtj" + \
    "xAj4UPI61oONK7zzFIu4gBfjJCndsZfdvG7h8wGjV98QhrKEnR7xKZ3KCr0_qR" + \
    "1B-gxpNk3xWU"

JWE_Authentication_Tag_5_7_4 = "DKW7jrb4WaRSNfbXVPlT5g"

JWE_compact_5_7_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_7_4,
                        JWE_Encrypted_Key_5_7_3,
                        JWE_IV_5_7_2,
                        JWE_Ciphertext_5_7_4,
                        JWE_Authentication_Tag_5_7_4)

JWE_general_5_7_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_7_3}],
    "protected": JWE_Protected_Header_5_7_4,
    "iv": JWE_IV_5_7_2,
    "ciphertext": JWE_Ciphertext_5_7_4,
    "tag": JWE_Authentication_Tag_5_7_4}

JWE_flattened_5_7_5 = {
    "protected": JWE_Protected_Header_5_7_4,
    "encrypted_key": JWE_Encrypted_Key_5_7_3,
    "iv": JWE_IV_5_7_2,
    "ciphertext": JWE_Ciphertext_5_7_4,
    "tag": JWE_Authentication_Tag_5_7_4}

# 5.8
AES_key_5_8_1 = {
    "kty": "oct",
    "kid": "81b20965-8332-43d9-a468-82160ad91ac8",
    "use": "enc",
    "alg": "A128KW",
    "k": "GZy6sIZ6wl9NJOKB-jnmVQ"}

JWE_IV_5_8_2 = "Qx0pmsDa8KnJc9Jo"

JWE_Encrypted_Key_5_8_3 = "CBI6oDw8MydIx1IBntf_lQcw2MmJKIQx"

JWE_Protected_Header_5_8_4 = \
    "eyJhbGciOiJBMTI4S1ciLCJraWQiOiI4MWIyMDk2NS04MzMyLTQzZDktYTQ2OC" + \
    "04MjE2MGFkOTFhYzgiLCJlbmMiOiJBMTI4R0NNIn0"

JWE_Ciphertext_5_8_4 = \
    "AwliP-KmWgsZ37BvzCefNen6VTbRK3QMA4TkvRkH0tP1bTdhtFJgJxeVmJkLD6" + \
    "1A1hnWGetdg11c9ADsnWgL56NyxwSYjU1ZEHcGkd3EkU0vjHi9gTlb90qSYFfe" + \
    "F0LwkcTtjbYKCsiNJQkcIp1yeM03OmuiYSoYJVSpf7ej6zaYcMv3WwdxDFl8RE" + \
    "wOhNImk2Xld2JXq6BR53TSFkyT7PwVLuq-1GwtGHlQeg7gDT6xW0JqHDPn_H-p" + \
    "uQsmthc9Zg0ojmJfqqFvETUxLAF-KjcBTS5dNy6egwkYtOt8EIHK-oEsKYtZRa" + \
    "a8Z7MOZ7UGxGIMvEmxrGCPeJa14slv2-gaqK0kEThkaSqdYw0FkQZF"

JWE_Authentication_Tag_5_8_4 = "ER7MWJZ1FBI_NKvn7Zb1Lw"

JWE_compact_5_8_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_8_4,
                        JWE_Encrypted_Key_5_8_3,
                        JWE_IV_5_8_2,
                        JWE_Ciphertext_5_8_4,
                        JWE_Authentication_Tag_5_8_4)

JWE_general_5_8_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_8_3}],
    "protected": JWE_Protected_Header_5_8_4,
    "iv": JWE_IV_5_8_2,
    "ciphertext": JWE_Ciphertext_5_8_4,
    "tag": JWE_Authentication_Tag_5_8_4}

JWE_flattened_5_8_5 = {
    "protected": JWE_Protected_Header_5_8_4,
    "encrypted_key": JWE_Encrypted_Key_5_8_3,
    "iv": JWE_IV_5_8_2,
    "ciphertext": JWE_Ciphertext_5_8_4,
    "tag": JWE_Authentication_Tag_5_8_4}

# 5.9
JWE_IV_5_9_2 = "p9pUq6XHY0jfEZIl"

JWE_Encrypted_Key_5_9_3 = "5vUT2WOtQxKWcekM_IzVQwkGgzlFDwPi"

JWE_Protected_Header_5_9_4 = \
    "eyJhbGciOiJBMTI4S1ciLCJraWQiOiI4MWIyMDk2NS04MzMyLTQzZDktYTQ2OC" + \
    "04MjE2MGFkOTFhYzgiLCJlbmMiOiJBMTI4R0NNIiwiemlwIjoiREVGIn0"

JWE_Ciphertext_5_9_4 = \
    "HbDtOsdai1oYziSx25KEeTxmwnh8L8jKMFNc1k3zmMI6VB8hry57tDZ61jXyez" + \
    "SPt0fdLVfe6Jf5y5-JaCap_JQBcb5opbmT60uWGml8blyiMQmOn9J--XhhlYg0" + \
    "m-BHaqfDO5iTOWxPxFMUedx7WCy8mxgDHj0aBMG6152PsM-w5E_o2B3jDbrYBK" + \
    "hpYA7qi3AyijnCJ7BP9rr3U8kxExCpG3mK420TjOw"

JWE_Authentication_Tag_5_9_4 = "VILuUwuIxaLVmh5X-T7kmA"

JWE_compact_5_9_5 = \
    "%s.%s.%s.%s.%s" % (JWE_Protected_Header_5_9_4,
                        JWE_Encrypted_Key_5_9_3,
                        JWE_IV_5_9_2,
                        JWE_Ciphertext_5_9_4,
                        JWE_Authentication_Tag_5_9_4)

JWE_general_5_9_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_9_3}],
    "protected": JWE_Protected_Header_5_9_4,
    "iv": JWE_IV_5_9_2,
    "ciphertext": JWE_Ciphertext_5_9_4,
    "tag": JWE_Authentication_Tag_5_9_4}

JWE_flattened_5_9_5 = {
    "protected": JWE_Protected_Header_5_9_4,
    "encrypted_key": JWE_Encrypted_Key_5_9_3,
    "iv": JWE_IV_5_9_2,
    "ciphertext": JWE_Ciphertext_5_9_4,
    "tag": JWE_Authentication_Tag_5_9_4}

# 5.10
AAD_5_10_1 = base64url_encode(json_encode(
    ["vcard",
     [["version", {}, "text", "4.0"],
      ["fn", {}, "text", "Meriadoc Brandybuck"],
      ["n", {}, "text", ["Brandybuck", "Meriadoc", "Mr.", ""]],
      ["bday", {}, "text", "TA 2982"],
      ["gender", {}, "text", "M"]]]))

JWE_IV_5_10_2 = "veCx9ece2orS7c_N"

JWE_Encrypted_Key_5_10_3 = "4YiiQ_ZzH76TaIkJmYfRFgOV9MIpnx4X"

JWE_Protected_Header_5_10_4 = \
    "eyJhbGciOiJBMTI4S1ciLCJraWQiOiI4MWIyMDk2NS04MzMyLTQzZDktYTQ2OC" + \
    "04MjE2MGFkOTFhYzgiLCJlbmMiOiJBMTI4R0NNIn0"

JWE_Ciphertext_5_10_4 = \
    "Z_3cbr0k3bVM6N3oSNmHz7Lyf3iPppGf3Pj17wNZqteJ0Ui8p74SchQP8xygM1" + \
    "oFRWCNzeIa6s6BcEtp8qEFiqTUEyiNkOWDNoF14T_4NFqF-p2Mx8zkbKxI7oPK" + \
    "8KNarFbyxIDvICNqBLba-v3uzXBdB89fzOI-Lv4PjOFAQGHrgv1rjXAmKbgkft" + \
    "9cB4WeyZw8MldbBhc-V_KWZslrsLNygon_JJWd_ek6LQn5NRehvApqf9ZrxB4a" + \
    "q3FXBxOxCys35PhCdaggy2kfUfl2OkwKnWUbgXVD1C6HxLIlqHhCwXDG59weHr" + \
    "RDQeHyMRoBljoV3X_bUTJDnKBFOod7nLz-cj48JMx3SnCZTpbQAkFV"

JWE_Authentication_Tag_5_10_4 = "vOaH_Rajnpy_3hOtqvZHRA"

JWE_general_5_10_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_10_3}],
    "protected": JWE_Protected_Header_5_10_4,
    "iv": JWE_IV_5_10_2,
    "aad": AAD_5_10_1,
    "ciphertext": JWE_Ciphertext_5_10_4,
    "tag": JWE_Authentication_Tag_5_10_4}

JWE_flattened_5_10_5 = {
    "protected": JWE_Protected_Header_5_10_4,
    "encrypted_key": JWE_Encrypted_Key_5_10_3,
    "iv": JWE_IV_5_10_2,
    "aad": AAD_5_10_1,
    "ciphertext": JWE_Ciphertext_5_10_4,
    "tag": JWE_Authentication_Tag_5_10_4}

# 5.11
JWE_IV_5_11_2 = "WgEJsDS9bkoXQ3nR"

JWE_Encrypted_Key_5_11_3 = "jJIcM9J-hbx3wnqhf5FlkEYos0sHsF0H"

JWE_Protected_Header_5_11_4 = "eyJlbmMiOiJBMTI4R0NNIn0"

JWE_Ciphertext_5_11_4 = \
    "lIbCyRmRJxnB2yLQOTqjCDKV3H30ossOw3uD9DPsqLL2DM3swKkjOwQyZtWsFL" + \
    "YMj5YeLht_StAn21tHmQJuuNt64T8D4t6C7kC9OCCJ1IHAolUv4MyOt80MoPb8" + \
    "fZYbNKqplzYJgIL58g8N2v46OgyG637d6uuKPwhAnTGm_zWhqc_srOvgiLkzyF" + \
    "XPq1hBAURbc3-8BqeRb48iR1-_5g5UjWVD3lgiLCN_P7AW8mIiFvUNXBPJK3nO" + \
    "WL4teUPS8yHLbWeL83olU4UAgL48x-8dDkH23JykibVSQju-f7e-1xreHWXzWL" + \
    "Hs1NqBbre0dEwK3HX_xM0LjUz77Krppgegoutpf5qaKg3l-_xMINmf"

JWE_Authentication_Tag_5_11_4 = "fNYLqpUe84KD45lvDiaBAQ"

JWE_Unprotected_Header_5_11_5 = {
    "alg": "A128KW",
    "kid": "81b20965-8332-43d9-a468-82160ad91ac8"}

JWE_general_5_11_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_11_3}],
    "unprotected": JWE_Unprotected_Header_5_11_5,
    "protected": JWE_Protected_Header_5_11_4,
    "iv": JWE_IV_5_11_2,
    "ciphertext": JWE_Ciphertext_5_11_4,
    "tag": JWE_Authentication_Tag_5_11_4}

JWE_flattened_5_11_5 = {
    "protected": JWE_Protected_Header_5_11_4,
    "unprotected": JWE_Unprotected_Header_5_11_5,
    "encrypted_key": JWE_Encrypted_Key_5_11_3,
    "iv": JWE_IV_5_11_2,
    "ciphertext": JWE_Ciphertext_5_11_4,
    "tag": JWE_Authentication_Tag_5_11_4}

# 5.11
JWE_IV_5_12_2 = "YihBoVOGsR1l7jCD"

JWE_Encrypted_Key_5_12_3 = "244YHfO_W7RMpQW81UjQrZcq5LSyqiPv"

JWE_Ciphertext_5_12_4 = \
    "qtPIMMaOBRgASL10dNQhOa7Gqrk7Eal1vwht7R4TT1uq-arsVCPaIeFwQfzrSS" + \
    "6oEUWbBtxEasE0vC6r7sphyVziMCVJEuRJyoAHFSP3eqQPb4Ic1SDSqyXjw_L3" + \
    "svybhHYUGyQuTmUQEDjgjJfBOifwHIsDsRPeBz1NomqeifVPq5GTCWFo5k_MNI" + \
    "QURR2Wj0AHC2k7JZfu2iWjUHLF8ExFZLZ4nlmsvJu_mvifMYiikfNfsZAudISO" + \
    "a6O73yPZtL04k_1FI7WDfrb2w7OqKLWDXzlpcxohPVOLQwpA3mFNRKdY-bQz4Z" + \
    "4KX9lfz1cne31N4-8BKmojpw-OdQjKdLOGkC445Fb_K1tlDQXw2sBF"

JWE_Authentication_Tag_5_12_4 = "e2m0Vm7JvjK2VpCKXS-kyg"

JWE_Unprotected_Header_5_12_5 = {
    "alg": "A128KW",
    "kid": "81b20965-8332-43d9-a468-82160ad91ac8",
    "enc": "A128GCM"}

JWE_general_5_12_5 = {
    "recipients": [{
        "encrypted_key": JWE_Encrypted_Key_5_12_3}],
    "unprotected": JWE_Unprotected_Header_5_12_5,
    "iv": JWE_IV_5_12_2,
    "ciphertext": JWE_Ciphertext_5_12_4,
    "tag": JWE_Authentication_Tag_5_12_4}

JWE_flattened_5_12_5 = {
    "unprotected": JWE_Unprotected_Header_5_12_5,
    "encrypted_key": JWE_Encrypted_Key_5_12_3,
    "iv": JWE_IV_5_12_2,
    "ciphertext": JWE_Ciphertext_5_12_4,
    "tag": JWE_Authentication_Tag_5_12_4}

# 5.13 - A256GCMKW not implemented yet


# In general we can't compare ciphertexts with the reference because
# either the algorithms use random nonces to authenticate the ciphertext
# or we randomly generate the nonce when we create the JWe.
# To double check implementation we encrypt/decrypt our own input and then
# decrypt the reference and check it against the given plaintext
class Cookbook08JWETests(unittest.TestCase):

    def test_5_1_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_1_4)
        rsa_key = jwk.JWK(**RSA_key_5_1_1)
        e = jwe.JWE(plaintext, protected,
                    algs=jwe.default_allowed_algs + ['RSA1_5'])
        e.add_recipient(rsa_key)
        enc = e.serialize()
        e.deserialize(enc, rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_1_5, rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_1_5), rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_1_5), rsa_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_2_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_2_4)
        rsa_key = jwk.JWK(**RSA_key_5_2_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(rsa_key)
        enc = e.serialize()
        e.deserialize(enc, rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_2_5, rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_2_5), rsa_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_2_5), rsa_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_3_encryption(self):
        plaintext = Payload_plaintext_5_3_1
        password = Password_5_3_1
        unicodepwd = Password_5_3_1.decode('utf8')
        e = jwe.JWE(plaintext, json_encode(JWE_Protected_Header_no_p2x))
        e.add_recipient(password)
        e.serialize(compact=True)
        enc = e.serialize()
        e.deserialize(enc, unicodepwd)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_3_5, password)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_3_5), unicodepwd)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_3_5), password)
        self.assertEqual(e.payload, plaintext)

    def test_5_4_encryption(self):
        plaintext = Payload_plaintext_5
        protected = json_encode(JWE_Protected_Header_no_epk_5_4_4)
        ec_key = jwk.JWK(**EC_key_5_4_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(ec_key)
        enc = e.serialize(compact=True)
        e.deserialize(enc, ec_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_4_5, ec_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_4_5), ec_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_5_encryption(self):
        plaintext = Payload_plaintext_5
        protected = json_encode(JWE_Protected_Header_no_epk_5_5_4)
        ec_key = jwk.JWK(**EC_key_5_5_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(ec_key)
        enc = e.serialize(compact=True)
        e.deserialize(enc, ec_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_5_5, ec_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_5_5), ec_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_6_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_6_3)
        aes_key = jwk.JWK(**AES_key_5_6_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(aes_key)
        e.serialize(compact=True)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_6_4, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_6_4), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_7_encryption(self):
        plaintext = Payload_plaintext_5
        aes_key = jwk.JWK(**AES_key_5_7_1)
        e = jwe.JWE(plaintext, json_encode(JWE_Protected_Header_no_ivtag))
        e.add_recipient(aes_key)
        enc = e.serialize(compact=True)
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_7_5, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_7_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_7_5), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_8_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_8_4)
        aes_key = jwk.JWK(**AES_key_5_8_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(aes_key)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_8_5, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_8_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_8_5), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_9_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_9_4)
        aes_key = jwk.JWK(**AES_key_5_8_1)
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(aes_key)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(JWE_compact_5_9_5, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_9_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_9_5), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_10_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_10_4)
        aad = base64url_decode(AAD_5_10_1)
        aes_key = jwk.JWK(**AES_key_5_8_1)
        e = jwe.JWE(plaintext, protected, aad=aad)
        e.add_recipient(aes_key)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_10_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_10_5), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_11_encryption(self):
        plaintext = Payload_plaintext_5
        protected = base64url_decode(JWE_Protected_Header_5_11_4)
        unprotected = json_encode(JWE_Unprotected_Header_5_11_5)
        aes_key = jwk.JWK(**AES_key_5_8_1)
        e = jwe.JWE(plaintext, protected, unprotected)
        e.add_recipient(aes_key)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_11_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_11_5), aes_key)
        self.assertEqual(e.payload, plaintext)

    def test_5_12_encryption(self):
        plaintext = Payload_plaintext_5
        unprotected = json_encode(JWE_Unprotected_Header_5_12_5)
        aes_key = jwk.JWK(**AES_key_5_8_1)
        e = jwe.JWE(plaintext, None, unprotected)
        e.add_recipient(aes_key)
        enc = e.serialize()
        e.deserialize(enc, aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_general_5_12_5), aes_key)
        self.assertEqual(e.payload, plaintext)
        e.deserialize(json_encode(JWE_flattened_5_12_5), aes_key)
        self.assertEqual(e.payload, plaintext)

# 5.13 - AES-GCM key wrapping not implemented yet
#     def test_5_13_encryption(self):
