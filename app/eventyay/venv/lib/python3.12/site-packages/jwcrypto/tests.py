# Copyright (C) 2015  JWCrypto Project Contributors - see LICENSE file

from __future__ import unicode_literals

import copy
import unittest

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import rsa

from jwcrypto import jwa
from jwcrypto import jwe
from jwcrypto import jwk
from jwcrypto import jws
from jwcrypto import jwt
from jwcrypto.common import InvalidJWSERegOperation
from jwcrypto.common import JWKeyNotFound
from jwcrypto.common import JWSEHeaderParameter
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.common import json_decode, json_encode

jwe_algs_and_rsa1_5 = jwe.default_allowed_algs + ['RSA1_5']

# RFC 7517 - A.1
PublicKeys = {"keys": [
              {"kty": "EC",
               "crv": "P-256",
               "x": "MKBCTNIcKUSDii11ySs3526iDZ8AiTo7Tu6KPAqv7D4",
               "y": "4Etl6SRW2YiLUrN5vfvVHuhp7x8PxltmWWlbbM4IFyM",
               "use": "enc",
               "kid": "1"},
              {"kty": "RSA",
               "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbf"
                    "AAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknj"
                    "hMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65"
                    "YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQ"
                    "vRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lF"
                    "d2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzK"
                    "nqDKgw",
               "e": "AQAB",
               "alg": "RS256",
               "kid": "2011-04-29"}],
              "thumbprints": ["cn-I_WNMClehiVp51i_0VpOENW1upEerA8sEam5hn-s",
                              "NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs"]}

# RFC 7517 - A.2
PrivateKeys = {"keys": [
               {"kty": "EC",
                "crv": "P-256",
                "x": "MKBCTNIcKUSDii11ySs3526iDZ8AiTo7Tu6KPAqv7D4",
                "y": "4Etl6SRW2YiLUrN5vfvVHuhp7x8PxltmWWlbbM4IFyM",
                "d": "870MB6gfuTJ4HtUnUvYMyJpr5eUZNP4Bk43bVdj3eAE",
                "use": "enc",
                "kid": "1"},
               {"kty": "RSA",
                "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbb"
                     "fAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3ok"
                     "njhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v"
                     "-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu"
                     "6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0"
                     "fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8a"
                     "wapJzKnqDKgw",
                "e": "AQAB",
                "d": "X4cTteJY_gn4FYPsXB8rdXix5vwsg1FLN5E3EaG6RJoVH-HLLKD9M7d"
                     "x5oo7GURknchnrRweUkC7hT5fJLM0WbFAKNLWY2vv7B6NqXSzUvxT0_"
                     "YSfqijwp3RTzlBaCxWp4doFk5N2o8Gy_nHNKroADIkJ46pRUohsXywb"
                     "ReAdYaMwFs9tv8d_cPVY3i07a3t8MN6TNwm0dSawm9v47UiCl3Sk5Zi"
                     "G7xojPLu4sbg1U2jx4IBTNBznbJSzFHK66jT8bgkuqsk0GjskDJk19Z"
                     "4qwjwbsnn4j2WBii3RL-Us2lGVkY8fkFzme1z0HbIkfz0Y6mqnOYtqc"
                     "0X4jfcKoAC8Q",
                "p": "83i-7IvMGXoMXCskv73TKr8637FiO7Z27zv8oj6pbWUQyLPQBQxtPVn"
                     "wD20R-60eTDmD2ujnMt5PoqMrm8RfmNhVWDtjjMmCMjOpSXicFHj7XO"
                     "uVIYQyqVWlWEh6dN36GVZYk93N8Bc9vY41xy8B9RzzOGVQzXvNEvn7O"
                     "0nVbfs",
                "q": "3dfOR9cuYq-0S-mkFLzgItgMEfFzB2q3hWehMuG0oCuqnb3vobLyumq"
                     "jVZQO1dIrdwgTnCdpYzBcOfW5r370AFXjiWft_NGEiovonizhKpo9VV"
                     "S78TzFgxkIdrecRezsZ-1kYd_s1qDbxtkDEgfAITAG9LUnADun4vIcb"
                     "6yelxk",
                "dp": "G4sPXkc6Ya9y8oJW9_ILj4xuppu0lzi_H7VTkS8xj5SdX3coE0oimY"
                      "wxIi2emTAue0UOa5dpgFGyBJ4c8tQ2VF402XRugKDTP8akYhFo5tAA"
                      "77Qe_NmtuYZc3C3m3I24G2GvR5sSDxUyAN2zq8Lfn9EUms6rY3Ob8Y"
                      "eiKkTiBj0",
                "dq": "s9lAH9fggBsoFR8Oac2R_E2gw282rT2kGOAhvIllETE1efrA6huUUv"
                      "MfBcMpn8lqeW6vzznYY5SSQF7pMdC_agI3nG8Ibp1BUb0JUiraRNqU"
                      "fLhcQb_d9GF4Dh7e74WbRsobRonujTYN1xCaP6TO61jvWrX-L18txX"
                      "w494Q_cgk",
                "qi": "GyM_p6JrXySiz1toFgKbWV-JdI3jQ4ypu9rbMWx3rQJBfmt0FoYzgU"
                      "IZEVFEcOqwemRN81zoDAaa-Bk0KWNGDjJHZDdDmFhW3AN7lI-puxk_"
                      "mHZGJ11rxyR8O55XLSe3SPmRfKwZI6yU24ZxvQKFYItdldUKGzO6Ia"
                      "6zTKhAVRU",
                "alg": "RS256",
                "kid": "2011-04-29"}]}

# RFC 7517 - A.3
SymmetricKeys = {"keys": [
                 {"kty": "oct",
                  "alg": "A128KW",
                  "k": "GawgguFyGrWKav7AX4VKUg"},
                 {"kty": "oct",
                  "k": "AyM1SysPpbyDfgZld3umj1qzKObwVMkoqQ-EstJQLr_T-1qS0gZH7"
                       "5aKtMN3Yj0iPS4hcgUuTwjAzZr1Z9CAow",
                  "kid": "HMAC key used in JWS A.1 example"}]}

# RFC 7517 - B
Useofx5c = {"kty": "RSA",
            "use": "sig",
            "kid": "1b94c",
            "n": "vrjOfz9Ccdgx5nQudyhdoR17V-IubWMeOZCwX_jj0hgAsz2J_pqYW08PLbK"
                 "_PdiVGKPrqzmDIsLI7sA25VEnHU1uCLNwBuUiCO11_-7dYbsr4iJmG0Qu2j"
                 "8DsVyT1azpJC_NG84Ty5KKthuCaPod7iI7w0LK9orSMhBEwwZDCxTWq4aYW"
                 "Achc8t-emd9qOvWtVMDC2BXksRngh6X5bUYLy6AyHKvj-nUy1wgzjYQDwHM"
                 "TplCoLtU-o-8SNnZ1tmRoGE9uJkBLdh5gFENabWnU5m1ZqZPdwS-qo-meMv"
                 "VfJb6jJVWRpl2SUtCnYG2C32qvbWbjZ_jBPD5eunqsIo1vQ",
            "e": "AQAB",
            "x5c": ["MIIDQjCCAiqgAwIBAgIGATz/FuLiMA0GCSqGSIb3DQEBBQUAMGIxCzAJ"
                    "BgNVBAYTAlVTMQswCQYDVQQIEwJDTzEPMA0GA1UEBxMGRGVudmVyMRww"
                    "GgYDVQQKExNQaW5nIElkZW50aXR5IENvcnAuMRcwFQYDVQQDEw5Ccmlh"
                    "biBDYW1wYmVsbDAeFw0xMzAyMjEyMzI5MTVaFw0xODA4MTQyMjI5MTVa"
                    "MGIxCzAJBgNVBAYTAlVTMQswCQYDVQQIEwJDTzEPMA0GA1UEBxMGRGVu"
                    "dmVyMRwwGgYDVQQKExNQaW5nIElkZW50aXR5IENvcnAuMRcwFQYDVQQD"
                    "Ew5CcmlhbiBDYW1wYmVsbDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC"
                    "AQoCggEBAL64zn8/QnHYMeZ0LncoXaEde1fiLm1jHjmQsF/449IYALM9"
                    "if6amFtPDy2yvz3YlRij66s5gyLCyO7ANuVRJx1NbgizcAblIgjtdf/u"
                    "3WG7K+IiZhtELto/A7Fck9Ws6SQvzRvOE8uSirYbgmj6He4iO8NCyvaK"
                    "0jIQRMMGQwsU1quGmFgHIXPLfnpnfajr1rVTAwtgV5LEZ4Iel+W1GC8u"
                    "gMhyr4/p1MtcIM42EA8BzE6ZQqC7VPqPvEjZ2dbZkaBhPbiZAS3YeYBR"
                    "DWm1p1OZtWamT3cEvqqPpnjL1XyW+oyVVkaZdklLQp2Btgt9qr21m42f"
                    "4wTw+Xrp6rCKNb0CAwEAATANBgkqhkiG9w0BAQUFAAOCAQEAh8zGlfSl"
                    "cI0o3rYDPBB07aXNswb4ECNIKG0CETTUxmXl9KUL+9gGlqCz5iWLOgWs"
                    "nrcKcY0vXPG9J1r9AqBNTqNgHq2G03X09266X5CpOe1zFo+Owb1zxtp3"
                    "PehFdfQJ610CDLEaS9V9Rqp17hCyybEpOGVwe8fnk+fbEL2Bo3UPGrps"
                    "HzUoaGpDftmWssZkhpBJKVMJyf/RuP2SmmaIzmnw9JiSlYhzo4tpzd5r"
                    "FXhjRbg4zW9C+2qok+2+qDM1iJ684gPHMIY8aLWrdgQTxkumGmTqgawR"
                    "+N5MDtdPTEQ0XfIBc2cJEUyMTY5MPvACWpkA6SdS4xSvdXK3IVfOWA=="
                    ]}

# RFC 7517 - C.1
RSAPrivateKey = {"kty": "RSA",
                 "kid": "juliet@capulet.lit",
                 "use": "enc",
                 "n": "t6Q8PWSi1dkJj9hTP8hNYFlvadM7DflW9mWepOJhJ66w7nyoK1gPNq"
                      "FMSQRyO125Gp-TEkodhWr0iujjHVx7BcV0llS4w5ACGgPrcAd6ZcSR"
                      "0-Iqom-QFcNP8Sjg086MwoqQU_LYywlAGZ21WSdS_PERyGFiNnj3QQ"
                      "lO8Yns5jCtLCRwLHL0Pb1fEv45AuRIuUfVcPySBWYnDyGxvjYGDSM-"
                      "AqWS9zIQ2ZilgT-GqUmipg0XOC0Cc20rgLe2ymLHjpHciCKVAbY5-L"
                      "32-lSeZO-Os6U15_aXrk9Gw8cPUaX1_I8sLGuSiVdt3C_Fn2PZ3Z8i"
                      "744FPFGGcG1qs2Wz-Q",
                 "e": "AQAB",
                 "d": "GRtbIQmhOZtyszfgKdg4u_N-R_mZGU_9k7JQ_jn1DnfTuMdSNprTea"
                      "STyWfSNkuaAwnOEbIQVy1IQbWVV25NY3ybc_IhUJtfri7bAXYEReWa"
                      "Cl3hdlPKXy9UvqPYGR0kIXTQRqns-dVJ7jahlI7LyckrpTmrM8dWBo"
                      "4_PMaenNnPiQgO0xnuToxutRZJfJvG4Ox4ka3GORQd9CsCZ2vsUDms"
                      "XOfUENOyMqADC6p1M3h33tsurY15k9qMSpG9OX_IJAXmxzAh_tWiZO"
                      "wk2K4yxH9tS3Lq1yX8C1EWmeRDkK2ahecG85-oLKQt5VEpWHKmjOi_"
                      "gJSdSgqcN96X52esAQ",
                 "p": "2rnSOV4hKSN8sS4CgcQHFbs08XboFDqKum3sc4h3GRxrTmQdl1ZK9u"
                      "w-PIHfQP0FkxXVrx-WE-ZEbrqivH_2iCLUS7wAl6XvARt1KkIaUxPP"
                      "SYB9yk31s0Q8UK96E3_OrADAYtAJs-M3JxCLfNgqh56HDnETTQhH3r"
                      "CT5T3yJws",
                 "q": "1u_RiFDP7LBYh3N4GXLT9OpSKYP0uQZyiaZwBtOCBNJgQxaj10RWjs"
                      "Zu0c6Iedis4S7B_coSKB0Kj9PaPaBzg-IySRvvcQuPamQu66riMhjV"
                      "tG6TlV8CLCYKrYl52ziqK0E_ym2QnkwsUX7eYTB7LbAHRK9GqocDE5"
                      "B0f808I4s",
                 "dp": "KkMTWqBUefVwZ2_Dbj1pPQqyHSHjj90L5x_MOzqYAJMcLMZtbUtwK"
                       "qvVDq3tbEo3ZIcohbDtt6SbfmWzggabpQxNxuBpoOOf_a_HgMXK_l"
                       "hqigI4y_kqS1wY52IwjUn5rgRrJ-yYo1h41KR-vz2pYhEAeYrhttW"
                       "txVqLCRViD6c",
                 "dq": "AvfS0-gRxvn0bwJoMSnFxYcK1WnuEjQFluMGfwGitQBWtfZ1Er7t1"
                       "xDkbN9GQTB9yqpDoYaN06H7CFtrkxhJIBQaj6nkF5KKS3TQtQ5qCz"
                       "kOkmxIe3KRbBymXxkb5qwUpX5ELD5xFc6FeiafWYY63TmmEAu_lRF"
                       "COJ3xDea-ots",
                 "qi": "lSQi-w9CpyUReMErP1RsBLk7wNtOvs5EQpPqmuMvqW57NBUczScEo"
                       "PwmUqqabu9V0-Py4dQ57_bapoKRu1R90bvuFnU63SHWEFglZQvJDM"
                       "eAvmj4sm-Fp0oYu_neotgQ0hzbI5gry7ajdYy9-2lNx_76aBZoOUu"
                       "9HCJ-UsfSOI8"}

# From
# vectors/cryptography_vectors/asymmetric/PEM_Serialization/rsa_private_key.pem
RSAPrivatePEM = b"""-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,B4B3C8C536E57CBE

B8Lq1K/wcOr4JMspWrX3zCX14WAp3xgHsKAB4XfuCuju/HQZoWXtok1xoi5e2Ovw
ENA99Jvb2yvBdDUfOlp1L1L+By3q+SwcdeNuEKjwGFG6MY2uZaVtLSiAFXf1N8PL
id7FMRGPIxpTtXKMhfAq4luRb0BgKh7+ZvM7LkxkRxF7M1XVQPGhrU0OfxX9VODe
YFH1q47os5JzHRcrRaFx6sn30e79ij2gRjzMVFuAX07n+yw3qeyNQNYdmDNP7iCZ
x//0iN0NboTI81coNlxx7TL4bYwgESt1c2i/TCfLITjKgEny7MKqU1/jTrOJWu85
PiK/ojaD1EMx9xxVgBCioQJVG/Jm9y+XhtGFAJUShzzsabX7KuANKRn3fgUN+yZS
yp8hmD+R5gQHJk/8+zZ6/Imv8W/G+7fPZuSMgWeWtDReCkfzgnyIdjaIp3Pdp5yN
WLLWADI4tHmNUqIzY7T25gVfg0P2tgQNzn3WzHxq4SfZN9Aw57woi8eSRpLBEn+C
JjqwTxtFQ14ynG6GPsBaDcAduchmJPL7e9PuAfFyLJuM8sU8QyB2oir1M/qYFhTC
ClXw2yylYjAy8TFw1L3UZA4hfAflINjYUY8pgAtTAjxeD/9PhiKSoMEX8Q/8Npti
1Db5RpAClIEdB6nPywj6BzC+6El3dSGaCV0sTQ42LD+S3QH8VCwTB2AuKq7zyuD6
wEQopcbIOGHSir875vYLmWLmqR9MCWZtKj/dWfTIQpBsPsI2ssZn/MptNqyEN9TW
GfnWoTuzoziCS5YmEq7Mh98fwP9Krb0abo3fFvu6CY3dhvvoxPaXahyAxBfpKArB
9nOf3gzHGReWNiFUtNZlvueYrC5CnblFzKaKB+81Imjw6RXM3QtuzbZ71zp+reL8
JeiwE/mriwuGbxTJx5gwQX48zA5PJ342CCrl7jMeIos5KXmYkWoU5hEuGM3tK4Lx
VAoGqcd/a4cWHuLWub8fbhFkIDcxFaMF8yQi0r2LOmvMOsv3RVpyfgJ07z5b9X1B
w76CYkjGqgr0EdU40VTPtNhtHq7rrJSzGbapRsFUpvqgnkEwUSdbY6bRknLETmfo
H3dPf2XQwXXPDMZTW54QsmQ9WjundqOFI2YsH6dCX/kmZK0IJVBpikL8SuM/ZJLK
LcYJcrNGetENEKKl6hDwTTIsG1y3gx6y3wPzBkyJ2DtMx9dPoCqYhPHsIGc/td0/
r4Ix9TWVLIl3MKq3z+/Hszd7jOnrkflfmKeA0DgJlqVJsuxP75pbdiKS/hCKRf8D
AFJLvt6JSGBnz9ZZCB4KrjpHK/k+X7p8Y65uc/aX5BLu8vyRqFduhg98GVXJmD7k
0ggXnqqFnies6SpnQ45cjfKSGDx/NjY0AwoGPH8n8CL6ZagU6K1utfHIMrqKkJME
F6KcPHWrQkECojLdMoDInnRirdRb/FcAadWBSPrf+6Nln4ilbBJIi8W/yzeM/WFj
UKKNjk4W26PGnNO6+TO5h1EpocDI4fx6UYIMmFjnyaLdLrSn1/SzuLL6I7pYZ0Um
8qI4aWjP9RiUvGYJirfAUjL5Vp9w4+osf1sGiioe0GH/1WVuHeQ93A==
-----END RSA PRIVATE KEY-----
"""

RSAPrivatePassword = b"123456"

# From
# vectors/cryptography_vectors/asymmetric/PEM_Serialization/rsa_public_key.pem
RSAPublicPEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnR4AZ+tgWYql+S3MaTQ6
zeIO1fKzFIoau9Q0zGuv/1oCAewXwxeDSSxw+/Z3GL1NpuuS9CpbR5EQ3d71bD0v
0G+Sf+mShSl0oljG7YqnNSPzKl+EQ3/KE+eEButcwas6KGof2BA4bFNCw/fPbuhk
u/d8sIIEgdzBMiGRMdW33uci3rsdOenMZQA7uWsM/q/pu85YLAVOxq6wlUCzP4FM
Tw/RKzayrPkn3Jfbqcy1aM2HDlFVx24vaN+RRbPSnVoQbo5EQYkUMXE8WmadSyHl
pXGRnWsJSV9AdGyDrbU+6tcFwcIwnW22jb/OJy8swHdqKGkuR1kQ0XqokK1yGKFZ
8wIDAQAB
-----END PUBLIC KEY-----
"""

# From cryptography/vectors/cryptography_vectors/x509/v1_cert.pem
PublicCert = b"""-----BEGIN CERTIFICATE-----
MIIBWzCCAQYCARgwDQYJKoZIhvcNAQEEBQAwODELMAkGA1UEBhMCQVUxDDAKBgNV
BAgTA1FMRDEbMBkGA1UEAxMSU1NMZWF5L3JzYSB0ZXN0IENBMB4XDTk1MDYxOTIz
MzMxMloXDTk1MDcxNzIzMzMxMlowOjELMAkGA1UEBhMCQVUxDDAKBgNVBAgTA1FM
RDEdMBsGA1UEAxMUU1NMZWF5L3JzYSB0ZXN0IGNlcnQwXDANBgkqhkiG9w0BAQEF
AANLADBIAkEAqtt6qS5GTxVxGZYWa0/4u+IwHf7p2LNZbcPBp9/OfIcYAXBQn8hO
/Re1uwLKXdCjIoaGs4DLdG88rkzfyK5dPQIDAQABMAwGCCqGSIb3DQIFBQADQQAE
Wc7EcF8po2/ZO6kNCwK/ICH6DobgLekA5lSLr5EvuioZniZp5lFzAw4+YzPQ7XKJ
zl9HYIMxATFyqSiD9jsx
-----END CERTIFICATE-----
"""

PublicCertThumbprint = '7KITkGJF74IZ9NKVvHfuJILbuIZny6j-roaNjB1vgiA'

# RFC 8037 - A.2
PublicKeys_EdDsa = {
    "keys": [
        {
            "kty": "OKP",
            "crv": "Ed25519",
            "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"
        },
    ],
    "thumbprints": ["kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"]
}

# RFC 8037 - A.1
PrivateKeys_EdDsa = {
    "keys": [
        {
            "kty": "OKP",
            "crv": "Ed25519",
            "d": "nWGxne_9WmC6hEr0kuwsxERJxWl7MmkZcDusAxyuf2A",
            "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"},
    ]
}

PublicKeys_secp256k1 = {
    "keys": [
        {
            "kty": "EC",
            "crv": "secp256k1",
            "x": "Ss6na3mcci8Ud4lQrjaB_T40sfKApEcl2RLIWOJdjow",
            "y": "7l9qIKtKPW6oEiOYBt7r22Sm0mtFJU-yBkkvMvpscd8"
        },
        {
            "kty": "EC",
            "crv": "P-256K",
            "x": "Ss6na3mcci8Ud4lQrjaB_T40sfKApEcl2RLIWOJdjow",
            "y": "7l9qIKtKPW6oEiOYBt7r22Sm0mtFJU-yBkkvMvpscd8"
        },
    ]
}

PrivateKeys_secp256k1 = {
    "keys": [
        {
            "kty": "EC",
            "crv": "secp256k1",
            "x": "Ss6na3mcci8Ud4lQrjaB_T40sfKApEcl2RLIWOJdjow",
            "y": "7l9qIKtKPW6oEiOYBt7r22Sm0mtFJU-yBkkvMvpscd8",
            "d": "GYhU2vrYGZrjLZn71Xniqm54Mi53xiYtaTLawzaf9dA"
        },
        {
            "kty": "EC",
            "crv": "P-256K",
            "x": "Ss6na3mcci8Ud4lQrjaB_T40sfKApEcl2RLIWOJdjow",
            "y": "7l9qIKtKPW6oEiOYBt7r22Sm0mtFJU-yBkkvMvpscd8",
            "d": "GYhU2vrYGZrjLZn71Xniqm54Mi53xiYtaTLawzaf9dA"
        }
    ]
}

PublicKeys_brainpool = {
    "keys": [
        {
            "kty": "EC",
            "crv": "BP-256",
            "x": "mpkJ29_CYAD0mzQ_MsrbjFMFYtcc9Oxpro37Fa4cLfI",
            "y": "iBfhNHk0cI73agNpjbKW62dvuVxn7kxp1Sm8oDnzHl8",
        },
        {
            "kty": "EC",
            "crv": "BP-384",
            "x": ("WZanneaC2Hi3xslA4znJv7otyEdV5dTPzNUvBjBXPM"
                  "ytf4mRY9JaAITdItjvUTAh"),
            "y": ("KNLRTNdvUg66aB_TVW4POZkE3q8S0YoQrCzYUrExRDe"
                  "_BXikkqIama-GYQ3UBOQL"),
        },
        {
            "kty": "EC",
            "crv": "BP-512",
            "x": ("aQXpvz7DH9OK5eFNO9dY3BdPY1v0-8Rg9KC322PY1Jy"
                  "BJq3EhT0uR_-tgbL2E_aGP6k56lF1xIOOtQxo8zziGA"),
            "y": ("l9XLHHncigOPr5Tvnj_mVzBFv6i7rdBQrLTq3RXZlCC"
                  "_f_q6L2o79K9IrN_J2wWxAfS8ekuGPGlHZUzK-3D9sA"),
        }
    ]
}

PrivateKeys_brainpool = {
    "keys": [
        {
            "kty": "EC",
            "crv": "BP-256",
            "x": "mpkJ29_CYAD0mzQ_MsrbjFMFYtcc9Oxpro37Fa4cLfI",
            "y": "iBfhNHk0cI73agNpjbKW62dvuVxn7kxp1Sm8oDnzHl8",
            "d": "KdKRgq0WEM97BQw3jpW_fTOep6fn-Samv4DfDNb-4s4"
        },
        {
            "kty": "EC",
            "crv": "BP-384",
            "x": ("WZanneaC2Hi3xslA4znJv7otyEdV5dTPzNUvBjBXPM"
                  "ytf4mRY9JaAITdItjvUTAh"),
            "y": ("KNLRTNdvUg66aB_TVW4POZkE3q8S0YoQrCzYUrExRDe"
                  "_BXikkqIama-GYQ3UBOQL"),
            "d": ("B5WeRV0-RztAPAhRbphSAUrsIzy-eSfWGSM5FxOQGlJ"
                  "cq-ECLA_-SIlH7NdWIEJY")
        },
        {
            "kty": "EC",
            "crv": "BP-512",
            "x": ("aQXpvz7DH9OK5eFNO9dY3BdPY1v0-8Rg9KC322PY1Jy"
                  "BJq3EhT0uR_-tgbL2E_aGP6k56lF1xIOOtQxo8zziGA"),
            "y": ("l9XLHHncigOPr5Tvnj_mVzBFv6i7rdBQrLTq3RXZlCC"
                  "_f_q6L2o79K9IrN_J2wWxAfS8ekuGPGlHZUzK-3D9sA"),
            "d": ("F_LJ9rebAjOtxoMUfngIywYsnJlZNjy3gxNAEvHjSkL"
                  "m6RUUdLXDwc50EMp0LeTh1ku039D5kldK3S9Xi0yKZA")
        }
    ]
}

Ed25519PrivatePEM = b"""-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIEh4ImJiiZgSNg9J9I+Z5toHKh6LDO2MCbSYNZTkMXDU
-----END PRIVATE KEY-----
"""

Ed25519PublicPEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAlsRcb1mVVIUcDjNqZU27N+iPXihH1EQDa/O3utHLtqc=
-----END PUBLIC KEY-----
"""

X25519PrivatePEM = b"""-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VuBCIEIBjAbPTtNY6CUuR5FG1+xb1u5nSRokrNaQYEsgu9O+hP
-----END PRIVATE KEY-----
"""

X25519PublicPEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VuAyEAW+m9ugi1psQFx6dtTl6J/XZ4JFP019S+oq4wyAoWPnQ=
-----END PUBLIC KEY-----
"""

ECPublicPEM = b"""-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEhvGzt82WMJxqTuXCZxnvwrx4enQj
6xc+erlhbTq8gTMAJBzNRPbpuj4NOwTCwjohrtY0TAkthwTuixuojpGKmw==
-----END PUBLIC KEY-----
"""

ECPublicJWK = {
    "crv": "P-256",
    "kid": "MWhDfZyDWdx6Fpk3N00ZMShuKhDRXw1fN4ZSfqzeAWY",
    "kty": "EC",
    "x": "hvGzt82WMJxqTuXCZxnvwrx4enQj6xc-erlhbTq8gTM",
    "y": "ACQczUT26bo-DTsEwsI6Ia7WNEwJLYcE7osbqI6Rips"
}

X25519PublicJWK = {
    'crv': 'X25519',
    'kid': '9cgLEZD5VsaV9dUPNehs2pOwxtmH-EWHJY-pC74Wjak',
    'kty': 'OKP',
    'x': 'W-m9ugi1psQFx6dtTl6J_XZ4JFP019S-oq4wyAoWPnQ'
}


class TestJWK(unittest.TestCase):
    def test_create_pubKeys(self):
        keylist = PublicKeys['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_priKeys(self):
        keylist = PrivateKeys['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_symKeys(self):
        keylist = SymmetricKeys['keys']
        for key in keylist:
            jwkey = jwk.JWK(**key)
            jwkey.get_op_key('sign')
            jwkey.get_op_key('verify')
            e = jwkey.export()
            self.assertEqual(json_decode(e), key)

        jwk.JWK(**Useofx5c)
        jwk.JWK(**RSAPrivateKey)

    def test_generate_keys(self):
        jwk.JWK.generate(kty='oct', size=256)
        jwk.JWK.generate(kty='RSA', size=4096)
        jwk.JWK.generate(kty='EC', curve='P-521')
        k = jwk.JWK.generate(kty='oct', alg='A192KW', kid='MySymmetricKey')
        self.assertEqual(k['kid'], 'MySymmetricKey')
        self.assertEqual(len(base64url_decode(k.get_op_key('encrypt'))), 24)
        jwk.JWK.generate(kty='RSA', alg='RS256')
        k = jwk.JWK.generate(kty='RSA', size=4096, alg='RS256')
        self.assertEqual(k.get_op_key('encrypt').key_size, 4096)

    def test_export_public_keys(self):
        k = jwk.JWK(**RSAPrivateKey)
        jk = k.export_public()
        self.assertFalse('d' in json_decode(jk))
        k2 = jwk.JWK(**json_decode(jk))
        self.assertEqual(k['kid'], k2['kid'])

    def test_generate_oct_key(self):
        key = jwk.JWK.generate(kty='oct', size=128)
        e = jwe.JWE('test', '{"alg":"A128KW","enc":"A128GCM"}')
        e.add_recipient(key)
        enc = e.serialize()
        e.deserialize(enc, key)
        self.assertEqual(e.payload.decode('utf-8'), 'test')

        # also test key generation with input_keysize != keysize
        key = jwk.JWK.generate(kty='oct', alg="A128CBC-HS256")
        self.assertEqual(len(base64url_decode(key['k'])), 32)
        e = jwe.JWE('test', '{"alg":"A256KW","enc":"A128CBC-HS256"}')
        e.add_recipient(key)
        enc = e.serialize()
        e.deserialize(enc, key)
        self.assertEqual(e.payload.decode('utf-8'), 'test')

    def test_generate_EC_key(self):
        # Backwards compat curve
        key = jwk.JWK.generate(kty='EC', curve='P-256')
        key.get_op_key('verify', 'P-256')
        # New param
        key = jwk.JWK.generate(kty='EC', crv='P-521')
        key.get_op_key('verify', 'P-521')
        # New param prevails
        key = jwk.JWK.generate(kty='EC', curve='P-256', crv='P-521')
        key.get_op_key('verify', 'P-521')
        # New secp256k curve
        key = jwk.JWK.generate(kty='EC', curve='secp256k1')
        key.get_op_key('verify', 'secp256k1')
        # Brainpool256R1 curve
        key = jwk.JWK.generate(kty='EC', crv='BP-256')
        key.get_op_key('verify', 'BP-256')
        # Brainpool384R1 curve
        key = jwk.JWK.generate(kty='EC', crv='BP-384')
        key.get_op_key('verify', 'BP-384')
        # Brainpool256R1 curve
        key = jwk.JWK.generate(kty='EC', crv='BP-512')
        key.get_op_key('verify', 'BP-512')

    def test_generate_OKP_keys(self):
        for crv in jwk.ImplementedOkpCurves:
            key = jwk.JWK.generate(kty='OKP', crv=crv)
            self.assertEqual(key['crv'], crv)

    def test_import_pyca_keys(self):
        rsa1 = rsa.generate_private_key(65537, 1024, default_backend())
        krsa1 = jwk.JWK.from_pyca(rsa1)
        self.assertEqual(krsa1['kty'], 'RSA')
        krsa2 = jwk.JWK.from_pyca(rsa1.public_key())
        self.assertEqual(krsa1.get_op_key('verify').public_numbers().n,
                         krsa2.get_op_key('verify').public_numbers().n)
        ec1 = ec.generate_private_key(ec.SECP256R1(), default_backend())
        kec1 = jwk.JWK.from_pyca(ec1)
        self.assertEqual(kec1['kty'], 'EC')
        kec2 = jwk.JWK.from_pyca(ec1.public_key())
        self.assertEqual(kec1.get_op_key('verify').public_numbers().x,
                         kec2.get_op_key('verify').public_numbers().x)
        self.assertRaises(jwk.InvalidJWKValue,
                          jwk.JWK.from_pyca, {})

    def test_jwk_from_json(self):
        k = jwk.JWK.generate(kty='oct', size=256)
        y = jwk.JWK.from_json(k.export())
        self.assertEqual(k.export(), y.export())

    def test_jwkset(self):
        k = jwk.JWK(**RSAPrivateKey)
        ks = jwk.JWKSet()
        ks.add(k)
        ks2 = jwk.JWKSet()
        ks2.import_keyset(ks.export())
        self.assertEqual(len(ks), len(ks2))
        self.assertEqual(len(ks), 1)
        k1 = ks.get_key(RSAPrivateKey['kid'])
        k2 = ks2.get_key(RSAPrivateKey['kid'])
        self.assertEqual(k1, k2)
        self.assertEqual(k1['d'], RSAPrivateKey['d'])
        # test class method import too
        ks3 = jwk.JWKSet.from_json(ks.export())
        self.assertEqual(len(ks), len(ks3))

        # Test key set with multiple keys
        ksm = jwk.JWKSet.from_json(json_encode(PrivateKeys))
        num = 0
        for item in ksm:
            self.assertTrue(isinstance(item, jwk.JWK))
            self.assertTrue(item in ksm)
            num += 1
        self.assertEqual(num, len(PrivateKeys['keys']))

    def test_jwkset_get_keys(self):
        # Test key set with multiple keys
        ksm = jwk.JWKSet.from_json(json_encode(PrivateKeys))
        k1 = jwk.JWK.from_json(json_encode(PrivateKeys['keys'][0]))
        kwargs = RSAPrivateKey.copy()
        kwargs['kid'] = '1'
        k2 = jwk.JWK(**kwargs)
        self.assertEqual(k1, ksm.get_key('1'))
        self.assertIsNone(ksm.get_key('not-there'))

        ksm.add(k2)
        self.assertEqual({k1, k2}, ksm.get_keys('1'))
        self.assertEqual(3, len(ksm['keys']))
        # Expect that duplicate kids will
        # raise an exception when we use get_key
        with self.assertRaises(jwk.InvalidJWKValue):
            ksm.get_key('1')

    def test_jwkset_issue_208(self):
        ks = jwk.JWKSet()
        key1 = RSAPrivateKey.copy()
        key1['kid'] = 'kid_1'
        ks.add(jwk.JWK(**key1))
        key2 = RSAPrivateKey.copy()
        key2['kid'] = 'kid_2'
        ks.add(jwk.JWK(**key2))
        ks2 = jwk.JWKSet()
        ks2.import_keyset(ks.export())
        self.assertEqual(len(ks['keys']), 2)
        self.assertEqual(len(ks['keys']), len(ks2['keys']))

    def test_thumbprint(self):
        for i in range(0, len(PublicKeys['keys'])):
            k = jwk.JWK(**PublicKeys['keys'][i])
            self.assertEqual(
                k.thumbprint(),
                PublicKeys['thumbprints'][i])

    def test_import_from_pem(self):
        pubk = jwk.JWK.from_pem(RSAPublicPEM)
        self.assertEqual(pubk.export_to_pem(), RSAPublicPEM)
        rsapub = pubk.get_op_key('verify')

        prik = jwk.JWK.from_pem(RSAPrivatePEM, password=RSAPrivatePassword)
        rsapri = prik.get_op_key('sign')
        self.assertEqual(rsapri.public_key().public_numbers().n,
                         rsapub.public_numbers().n)

        pubc = jwk.JWK.from_pem(PublicCert)
        self.assertEqual(pubc['kid'], PublicCertThumbprint)

    def test_import_ec_from_pem(self):
        pub_ec = jwk.JWK.from_pem(ECPublicPEM)
        self.assertEqual(pub_ec.export_to_pem(), ECPublicPEM)
        self.assertEqual(json_decode(pub_ec.export()), ECPublicJWK)

    def test_import_x25519_from_pem(self):
        pub_x25519 = jwk.JWK.from_pem(X25519PublicPEM)
        self.assertEqual(pub_x25519.export_to_pem(), X25519PublicPEM)
        self.assertEqual(json_decode(pub_x25519.export()), X25519PublicJWK)

    def test_export_symmetric(self):
        key = jwk.JWK(**SymmetricKeys['keys'][0])
        self.assertTrue(key.is_symmetric)
        self.assertFalse(key.has_public)
        self.assertFalse(key.has_private)
        self.assertEqual(json_encode(SymmetricKeys['keys'][0]),
                         key.export_symmetric())

    def test_export_public(self):
        key = jwk.JWK.from_pem(PublicCert)
        self.assertFalse(key.is_symmetric)
        self.assertTrue(key.has_public)
        self.assertFalse(key.has_private)
        pubc = key.export_public()
        self.assertEqual(json_decode(pubc)["kid"], PublicCertThumbprint)

    def test_export_private(self):
        key = jwk.JWK.from_pem(RSAPrivatePEM, password=RSAPrivatePassword)
        self.assertFalse(key.is_symmetric)
        self.assertTrue(key.has_public)
        self.assertTrue(key.has_private)
        pri = key.export_private()
        prikey = jwk.JWK(**json_decode(pri))
        self.assertTrue(prikey.has_private)
        pub = key.export_public()
        pubkey = jwk.JWK(**json_decode(pub))
        self.assertFalse(pubkey.has_private)
        self.assertEqual(prikey['kid'], pubkey['kid'])

    def test_export_as_dict(self):
        key = jwk.JWK(**SymmetricKeys['keys'][1])
        k = key.export_symmetric(as_dict=True)
        self.assertEqual(k['kid'], SymmetricKeys['keys'][1]['kid'])
        key = jwk.JWK.from_pem(PublicCert)
        k = key.export_public(as_dict=True)
        self.assertEqual(k['kid'], PublicCertThumbprint)
        key = jwk.JWK.from_pem(RSAPrivatePEM, password=RSAPrivatePassword)
        k = key.export_private(as_dict=True)
        self.assertEqual(k['kid'],
                         'x31vrbZceU2qOPLtrUwPkLa3PNakMn9tOsq_ntFVrJc')
        keyset = jwk.JWKSet.from_json(json_encode(PrivateKeys))
        ks = keyset.export(as_dict=True)
        self.assertTrue('keys' in ks)

    def test_public(self):
        key = jwk.JWK.from_pem(RSAPrivatePEM, password=RSAPrivatePassword)
        self.assertTrue(key.has_public)
        self.assertTrue(key.has_private)
        pubkey = key.public()
        self.assertTrue(pubkey.has_public)
        self.assertFalse(pubkey.has_private)
        # finally check public works
        e = jwe.JWE('plaintext', '{"alg":"RSA-OAEP","enc":"A256GCM"}')
        e.add_recipient(pubkey)
        enc = e.serialize()
        d = jwe.JWE()
        d.deserialize(enc, key)
        self.assertEqual(d.payload, b'plaintext')

    def test_invalid_value(self):
        with self.assertRaises(jwk.InvalidJWKValue):
            jwk.JWK(kty='oct', k=b'\x01')

    def test_create_pubKeys_eddsa(self):
        keylist = PublicKeys_EdDsa['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_priKeys_eddsa(self):
        keylist = PrivateKeys_EdDsa['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_pubKeys_secp256k1(self):
        keylist = PublicKeys_secp256k1['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_priKeys_secp256k1(self):
        keylist = PrivateKeys_secp256k1['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_pubKeys_brainpool(self):
        keylist = PublicKeys_brainpool['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_create_priKeys_brainpool(self):
        keylist = PrivateKeys_brainpool['keys']
        for key in keylist:
            jwk.JWK(**key)

    def test_thumbprint_eddsa(self):
        for i in range(0, len(PublicKeys_EdDsa['keys'])):
            k = jwk.JWK(**PublicKeys_EdDsa['keys'][i])
            self.assertEqual(
                k.thumbprint(),
                PublicKeys_EdDsa['thumbprints'][i])

    def test_pem_okp(self):
        payload = b'Imported private Ed25519'
        prikey = jwk.JWK.from_pem(Ed25519PrivatePEM)
        self.assertTrue(prikey.has_private)
        self.assertTrue(prikey.has_public)
        s = jws.JWS(payload)
        s.add_signature(prikey, None, {'alg': 'EdDSA'}, None)
        sig = s.serialize()
        pubkey = jwk.JWK.from_pem(Ed25519PublicPEM)
        self.assertTrue(pubkey.has_public)
        self.assertFalse(pubkey.has_private)
        jws_token = jws.JWS()
        jws_token.deserialize(sig, pubkey, alg="EdDSA")
        self.assertTrue(jws_token.objects['valid'])
        self.assertEqual(jws_token.payload, payload)

    def test_jwk_as_dict(self):
        key = jwk.JWK(**PublicKeys['keys'][0])
        self.assertEqual(key['kty'], 'EC')
        self.assertEqual(key.kty, 'EC')
        self.assertEqual(key.x, key['x'])
        self.assertEqual(key.kid, '1')
        key = jwk.JWK(**PublicKeys['keys'][1])
        self.assertEqual(key['kty'], 'RSA')
        self.assertEqual(key.n, key['n'])
        with self.assertRaises(AttributeError):
            # pylint: disable=pointless-statement
            key.d
        with self.assertRaises(AttributeError):
            key.x = 'xyz'
        with self.assertRaises(jwk.InvalidJWKValue):
            key['n'] = '!!!'
        with self.assertRaises(jwk.InvalidJWKValue):
            key.e = '3'
        key.unknown = '1'
        key['unknown'] = 2
        self.assertFalse(key.unknown == key['unknown'])

    def test_jwk_from_password(self):
        key = jwk.JWK.from_password('test password')
        self.assertEqual(key['kty'], 'oct')
        self.assertEqual(key['k'], 'dGVzdCBwYXNzd29yZA')

    def test_p256k_alias(self):
        key = jwk.JWK.generate(kty='EC', curve='P-256K')
        key.get_op_key('verify', 'secp256k1')

        pub_k = jwk.JWK(**PrivateKeys_secp256k1['keys'][0])
        pri_k = jwk.JWK(**PrivateKeys_secp256k1['keys'][1])
        payload = bytes(bytearray(A1_payload))
        test = jws.JWS(payload)
        test.add_signature(pri_k, None, json_encode({"alg": "ES256K"}), None)
        test_serialization_compact = test.serialize(compact=True)
        verify = jws.JWS()
        verify.deserialize(test_serialization_compact)
        verify.verify(pub_k.public())
        self.assertEqual(verify.payload, payload)

    def test_thumbprint_uri(self):
        k = jwk.JWK(**PublicKeys['keys'][1])
        self.assertEqual(
            k.thumbprint_uri(),
            "urn:ietf:params:oauth:jwk-thumbprint:sha-256:{}".format(
                PublicKeys['thumbprints'][1]))


# RFC 7515 - A.1
A1_protected = \
    [123, 34, 116, 121, 112, 34, 58, 34, 74, 87, 84, 34, 44, 13, 10, 32,
     34, 97, 108, 103, 34, 58, 34, 72, 83, 50, 53, 54, 34, 125]
A1_payload = \
    [123, 34, 105, 115, 115, 34, 58, 34, 106, 111, 101, 34, 44, 13, 10,
     32, 34, 101, 120, 112, 34, 58, 49, 51, 48, 48, 56, 49, 57, 51, 56,
     48, 44, 13, 10, 32, 34, 104, 116, 116, 112, 58, 47, 47, 101, 120, 97,
     109, 112, 108, 101, 46, 99, 111, 109, 47, 105, 115, 95, 114, 111,
     111, 116, 34, 58, 116, 114, 117, 101, 125]
A1_signature = \
    [116, 24, 223, 180, 151, 153, 224, 37, 79, 250, 96, 125, 216, 173,
     187, 186, 22, 212, 37, 77, 105, 214, 191, 240, 91, 88, 5, 88, 83,
     132, 141, 121]
A1_example = {'key': SymmetricKeys['keys'][1],
              'alg': 'HS256',
              'protected': bytes(bytearray(A1_protected)).decode('utf-8'),
              'payload': bytes(bytearray(A1_payload)),
              'signature': bytes(bytearray(A1_signature))}

# RFC 7515 - A.2
A2_protected = \
    [123, 34, 97, 108, 103, 34, 58, 34, 82, 83, 50, 53, 54, 34, 125]
A2_payload = A1_payload
A2_key = \
    {"kty": "RSA",
     "n": "ofgWCuLjybRlzo0tZWJjNiuSfb4p4fAkd_wWJcyQoTbji9k0l8W26mPddx"
          "HmfHQp-Vaw-4qPCJrcS2mJPMEzP1Pt0Bm4d4QlL-yRT-SFd2lZS-pCgNMs"
          "D1W_YpRPEwOWvG6b32690r2jZ47soMZo9wGzjb_7OMg0LOL-bSf63kpaSH"
          "SXndS5z5rexMdbBYUsLA9e-KXBdQOS-UTo7WTBEMa2R2CapHg665xsmtdV"
          "MTBQY4uDZlxvb3qCo5ZwKh9kG4LT6_I5IhlJH7aGhyxXFvUK-DWNmoudF8"
          "NAco9_h9iaGNj8q2ethFkMLs91kzk2PAcDTW9gb54h4FRWyuXpoQ",
     "e": "AQAB",
     "d": "Eq5xpGnNCivDflJsRQBXHx1hdR1k6Ulwe2JZD50LpXyWPEAeP88vLNO97I"
          "jlA7_GQ5sLKMgvfTeXZx9SE-7YwVol2NXOoAJe46sui395IW_GO-pWJ1O0"
          "BkTGoVEn2bKVRUCgu-GjBVaYLU6f3l9kJfFNS3E0QbVdxzubSu3Mkqzjkn"
          "439X0M_V51gfpRLI9JYanrC4D4qAdGcopV_0ZHHzQlBjudU2QvXt4ehNYT"
          "CBr6XCLQUShb1juUO1ZdiYoFaFQT5Tw8bGUl_x_jTj3ccPDVZFD9pIuhLh"
          "BOneufuBiB4cS98l2SR_RQyGWSeWjnczT0QU91p1DhOVRuOopznQ",
     "p": "4BzEEOtIpmVdVEZNCqS7baC4crd0pqnRH_5IB3jw3bcxGn6QLvnEtfdUdi"
          "YrqBdss1l58BQ3KhooKeQTa9AB0Hw_Py5PJdTJNPY8cQn7ouZ2KKDcmnPG"
          "BY5t7yLc1QlQ5xHdwW1VhvKn-nXqhJTBgIPgtldC-KDV5z-y2XDwGUc",
     "q": "uQPEfgmVtjL0Uyyx88GZFF1fOunH3-7cepKmtH4pxhtCoHqpWmT8YAmZxa"
          "ewHgHAjLYsp1ZSe7zFYHj7C6ul7TjeLQeZD_YwD66t62wDmpe_HlB-TnBA"
          "-njbglfIsRLtXlnDzQkv5dTltRJ11BKBBypeeF6689rjcJIDEz9RWdc",
     "dp": "BwKfV3Akq5_MFZDFZCnW-wzl-CCo83WoZvnLQwCTeDv8uzluRSnm71I3Q"
           "CLdhrqE2e9YkxvuxdBfpT_PI7Yz-FOKnu1R6HsJeDCjn12Sk3vmAktV2zb"
           "34MCdy7cpdTh_YVr7tss2u6vneTwrA86rZtu5Mbr1C1XsmvkxHQAdYo0",
     "dq": "h_96-mK1R_7glhsum81dZxjTnYynPbZpHziZjeeHcXYsXaaMwkOlODsWa"
           "7I9xXDoRwbKgB719rrmI2oKr6N3Do9U0ajaHF-NKJnwgjMd2w9cjz3_-ky"
           "NlxAr2v4IKhGNpmM5iIgOS1VZnOZ68m6_pbLBSp3nssTdlqvd0tIiTHU",
     "qi": "IYd7DHOhrWvxkwPQsRM2tOgrjbcrfvtQJipd-DlcxyVuuM9sQLdgjVk2o"
           "y26F0EmpScGLq2MowX7fhd_QJQ3ydy5cY7YIBi87w93IKLEdfnbJtoOPLU"
           "W0ITrJReOgo1cq9SbsxYawBgfp_gh6A5603k2-ZQwVK0JKSHuLFkuQ3U"}
A2_signature = \
    [112, 46, 33, 137, 67, 232, 143, 209, 30, 181, 216, 45, 191, 120, 69,
     243, 65, 6, 174, 27, 129, 255, 247, 115, 17, 22, 173, 209, 113, 125,
     131, 101, 109, 66, 10, 253, 60, 150, 238, 221, 115, 162, 102, 62, 81,
     102, 104, 123, 0, 11, 135, 34, 110, 1, 135, 237, 16, 115, 249, 69,
     229, 130, 173, 252, 239, 22, 216, 90, 121, 142, 232, 198, 109, 219,
     61, 184, 151, 91, 23, 208, 148, 2, 190, 237, 213, 217, 217, 112, 7,
     16, 141, 178, 129, 96, 213, 248, 4, 12, 167, 68, 87, 98, 184, 31,
     190, 127, 249, 217, 46, 10, 231, 111, 36, 242, 91, 51, 187, 230, 244,
     74, 230, 30, 177, 4, 10, 203, 32, 4, 77, 62, 249, 18, 142, 212, 1,
     48, 121, 91, 212, 189, 59, 65, 238, 202, 208, 102, 171, 101, 25, 129,
     253, 228, 141, 247, 127, 55, 45, 195, 139, 159, 175, 221, 59, 239,
     177, 139, 93, 163, 204, 60, 46, 176, 47, 158, 58, 65, 214, 18, 202,
     173, 21, 145, 18, 115, 160, 95, 35, 185, 232, 56, 250, 175, 132, 157,
     105, 132, 41, 239, 90, 30, 136, 121, 130, 54, 195, 212, 14, 96, 69,
     34, 165, 68, 200, 242, 122, 122, 45, 184, 6, 99, 209, 108, 247, 202,
     234, 86, 222, 64, 92, 178, 33, 90, 69, 178, 194, 85, 102, 181, 90,
     193, 167, 72, 160, 112, 223, 200, 163, 42, 70, 149, 67, 208, 25, 238,
     251, 71]
A2_example = {'key': A2_key,
              'alg': 'RS256',
              'protected': bytes(bytearray(A2_protected)).decode('utf-8'),
              'payload': bytes(bytearray(A2_payload)),
              'signature': bytes(bytearray(A2_signature))}

# RFC 7515 - A.3
A3_protected = \
    [123, 34, 97, 108, 103, 34, 58, 34, 69, 83, 50, 53, 54, 34, 125]
A3_payload = A2_payload
A3_key = \
    {"kty": "EC",
     "crv": "P-256",
     "x": "f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU",
     "y": "x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0",
     "d": "jpsQnnGQmL-YBIffH1136cspYG6-0iY7X1fCE9-E9LI"}
A3_signature = \
    [14, 209, 33, 83, 121, 99, 108, 72, 60, 47, 127, 21, 88,
     7, 212, 2, 163, 178, 40, 3, 58, 249, 124, 126, 23, 129,
     154, 195, 22, 158, 166, 101] + \
    [197, 10, 7, 211, 140, 60, 112, 229, 216, 241, 45, 175,
     8, 74, 84, 128, 166, 101, 144, 197, 242, 147, 80, 154,
     143, 63, 127, 138, 131, 163, 84, 213]
A3_example = {'key': A3_key,
              'alg': 'ES256',
              'protected': bytes(bytearray(A3_protected)).decode('utf-8'),
              'payload': bytes(bytearray(A3_payload)),
              'signature': bytes(bytearray(A3_signature))}


# RFC 7515 - A.4
A4_protected = \
    [123, 34, 97, 108, 103, 34, 58, 34, 69, 83, 53, 49, 50, 34, 125]
A4_payload = [80, 97, 121, 108, 111, 97, 100]
A4_key = \
    {"kty": "EC",
     "crv": "P-521",
     "x": "AekpBQ8ST8a8VcfVOTNl353vSrDCLLJXmPk06wTjxrrjcBpXp5EOnYG_"
          "NjFZ6OvLFV1jSfS9tsz4qUxcWceqwQGk",
     "y": "ADSmRA43Z1DSNx_RvcLI87cdL07l6jQyyBXMoxVg_l2Th-x3S1WDhjDl"
          "y79ajL4Kkd0AZMaZmh9ubmf63e3kyMj2",
     "d": "AY5pb7A0UFiB3RELSD64fTLOSV_jazdF7fLYyuTw8lOfRhWg6Y6rUrPA"
          "xerEzgdRhajnu0ferB0d53vM9mE15j2C"}
A4_signature = \
    [1, 220, 12, 129, 231, 171, 194, 209, 232, 135, 233, 117, 247, 105,
     122, 210, 26, 125, 192, 1, 217, 21, 82, 91, 45, 240, 255, 83, 19,
     34, 239, 71, 48, 157, 147, 152, 105, 18, 53, 108, 163, 214, 68,
     231, 62, 153, 150, 106, 194, 164, 246, 72, 143, 138, 24, 50, 129,
     223, 133, 206, 209, 172, 63, 237, 119, 109] + \
    [0, 111, 6, 105, 44, 5, 41, 208, 128, 61, 152, 40, 92, 61, 152, 4,
     150, 66, 60, 69, 247, 196, 170, 81, 193, 199, 78, 59, 194, 169,
     16, 124, 9, 143, 42, 142, 131, 48, 206, 238, 34, 175, 83, 203,
     220, 159, 3, 107, 155, 22, 27, 73, 111, 68, 68, 21, 238, 144, 229,
     232, 148, 188, 222, 59, 242, 103]
A4_example = {'key': A4_key,
              'alg': 'ES512',
              'protected': bytes(bytearray(A4_protected)).decode('utf-8'),
              'payload': bytes(bytearray(A4_payload)),
              'signature': bytes(bytearray(A4_signature))}


# RFC 7515 - A.4
A5_protected = 'eyJhbGciOiJub25lIn0'
A5_payload = A2_payload
A5_key = \
    {"kty": "oct", "k": ""}
A5_signature = b''
A5_example = {'key': A5_key,
              'alg': 'none',
              'protected': base64url_decode(A5_protected).decode('utf-8'),
              'payload': bytes(bytearray(A5_payload)),
              'signature': A5_signature}

A6_serialized = \
    '{' + \
    '"payload":' + \
    '"eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGF' + \
    'tcGxlLmNvbS9pc19yb290Ijp0cnVlfQ",' + \
    '"signatures":[' + \
    '{"protected":"eyJhbGciOiJSUzI1NiJ9",' + \
    '"header":' + \
    '{"kid":"2010-12-29"},' + \
    '"signature":' + \
    '"cC4hiUPoj9Eetdgtv3hF80EGrhuB__dzERat0XF9g2VtQgr9PJbu3XOiZj5RZ' + \
    'mh7AAuHIm4Bh-0Qc_lF5YKt_O8W2Fp5jujGbds9uJdbF9CUAr7t1dnZcAcQjb' + \
    'KBYNX4BAynRFdiuB--f_nZLgrnbyTyWzO75vRK5h6xBArLIARNPvkSjtQBMHl' + \
    'b1L07Qe7K0GarZRmB_eSN9383LcOLn6_dO--xi12jzDwusC-eOkHWEsqtFZES' + \
    'c6BfI7noOPqvhJ1phCnvWh6IeYI2w9QOYEUipUTI8np6LbgGY9Fs98rqVt5AX' + \
    'LIhWkWywlVmtVrBp0igcN_IoypGlUPQGe77Rw"},' + \
    '{"protected":"eyJhbGciOiJFUzI1NiJ9",' + \
    '"header":' + \
    '{"kid":"e9bc097a-ce51-4036-9562-d2ade882db0d"},' + \
    '"signature":' + \
    '"DtEhU3ljbEg8L38VWAfUAqOyKAM6-Xx-F4GawxaepmXFCgfTjDxw5djxLa8IS' + \
    'lSApmWQxfKTUJqPP3-Kg6NU1Q"}]' + \
    '}'
A6_example = {
    'payload': bytes(bytearray(A2_payload)),
    'key1': jwk.JWK(**A2_key),
    'protected1': bytes(bytearray(A2_protected)).decode('utf-8'),
    'header1': json_encode({"kid": "2010-12-29"}),
    'key2': jwk.JWK(**A3_key),
    'protected2': bytes(bytearray(A3_protected)).decode('utf-8'),
    'header2': json_encode({"kid": "e9bc097a-ce51-4036-9562-d2ade882db0d"}),
    'serialized': A6_serialized,
    'jose_header': [{"kid": "2010-12-29",
                     "alg": "RS256"},
                    {"kid": "e9bc097a-ce51-4036-9562-d2ade882db0d",
                     "alg": "ES256"}]}

A7_example = \
    '{' + \
    '"payload":' + \
    '"eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGF' + \
    'tcGxlLmNvbS9pc19yb290Ijp0cnVlfQ",' + \
    '"protected":"eyJhbGciOiJFUzI1NiJ9",' + \
    '"header":' + \
    '{"kid":"e9bc097a-ce51-4036-9562-d2ade882db0d"},' + \
    '"signature":' + \
    '"DtEhU3ljbEg8L38VWAfUAqOyKAM6-Xx-F4GawxaepmXFCgfTjDxw5djxLa8IS' + \
    'lSApmWQxfKTUJqPP3-Kg6NU1Q"' + \
    '}'

E_negative = \
    'eyJhbGciOiJub25lIiwNCiAiY3JpdCI6WyJodHRwOi8vZXhhbXBsZS5jb20vVU5ERU' + \
    'ZJTkVEIl0sDQogImh0dHA6Ly9leGFtcGxlLmNvbS9VTkRFRklORUQiOnRydWUNCn0.' + \
    'RkFJTA.'

customhdr_jws_example = \
    '{' + \
    '"payload":' + \
    '"eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGF' + \
    'tcGxlLmNvbS9pc19yb290Ijp0cnVlfQ",' + \
    '"protected":"eyJhbGciOiJFUzI1NiJ9",' + \
    '"header":' + \
    '{"kid":"e9bc097a-ce51-4036-9562-d2ade882db0d", ' + \
    '"custom1":"custom_val"},' + \
    '"signature":' + \
    '"DtEhU3ljbEg8L38VWAfUAqOyKAM6-Xx-F4GawxaepmXFCgfTjDxw5djxLa8IS' + \
    'lSApmWQxfKTUJqPP3-Kg6NU1Q"' + \
    '}'


class TestJWS(unittest.TestCase):
    def check_sign(self, test):
        s = jws.JWSCore(test['alg'],
                        jwk.JWK(**test['key']),
                        test['protected'],
                        test['payload'],
                        test.get('allowed_algs', None))
        sig = s.sign()
        decsig = base64url_decode(sig['signature'])
        s.verify(decsig)
        # ECDSA signatures are always different every time
        # they are generated unlike RSA or symmetric ones
        if test['key']['kty'] != 'EC':
            self.assertEqual(decsig, test['signature'])
        else:
            # Check we can verify the test signature independently
            # this is so that we can test the ECDSA against a known
            # good signature
            s.verify(test['signature'])

    def test_A1(self):
        self.check_sign(A1_example)

    def test_A2(self):
        self.check_sign(A2_example)

    def test_A3(self):
        self.check_sign(A3_example)

    def test_A4(self):
        self.check_sign(A4_example)

    def test_A5(self):
        self.assertRaises(jws.InvalidJWSOperation,
                          self.check_sign, A5_example)
        a5_bis = {'allowed_algs': ['none']}
        a5_bis.update(A5_example)
        self.check_sign(a5_bis)

    def test_A6(self):
        s = jws.JWS(A6_example['payload'])
        s.add_signature(A6_example['key1'], None,
                        A6_example['protected1'],
                        A6_example['header1'])
        s.add_signature(A6_example['key2'], None,
                        A6_example['protected2'],
                        A6_example['header2'])
        s.verify(A6_example['key1'])
        s.verify(A6_example['key2'])
        sig = s.serialize()
        s.deserialize(sig, A6_example['key1'])
        s.deserialize(A6_serialized, A6_example['key2'])
        self.assertEqual(A6_example['jose_header'], s.jose_header)

    def test_A7(self):
        s = jws.JWS(A6_example['payload'])
        s.deserialize(A7_example, A6_example['key2'])

    def test_E(self):
        s = jws.JWS(A6_example['payload'])
        with self.assertRaises(jws.InvalidJWSSignature):
            s.deserialize(E_negative)
            s.verify(None)

    def test_customhdr_jws(self):
        # Test pass header check
        def jws_chk1(jwobj):
            return jwobj.jose_header['custom1'] == 'custom_val'

        newhdr = JWSEHeaderParameter('Custom header 1', False, True, jws_chk1)
        newreg = {'custom1': newhdr}
        s = jws.JWS(A6_example['payload'], header_registry=newreg)
        s.deserialize(customhdr_jws_example, A6_example['key2'])

        # Test fail header check
        def jws_chk2(jwobj):
            return jwobj.jose_header['custom1'] == 'custom_not'

        newhdr = JWSEHeaderParameter('Custom header 1', False, True, jws_chk2)
        newreg = {'custom1': newhdr}
        s = jws.JWS(A6_example['payload'], header_registry=newreg)
        with self.assertRaises(jws.InvalidJWSSignature):
            s.deserialize(customhdr_jws_example, A6_example['key2'])

    def test_customhdr_jws_exists(self):
        newhdr = JWSEHeaderParameter('Custom header 1', False, True, None)
        newreg = {'alg': newhdr}
        with self.assertRaises(InvalidJWSERegOperation):
            jws.JWS(A6_example['payload'], header_registry=newreg)

    def test_EdDsa_signing_and_verification(self):
        examples = []
        if 'Ed25519' in jwk.ImplementedOkpCurves:
            examples = [E_Ed25519]
        for curve_example in examples:
            key = jwk.JWK.from_json(curve_example['key_json'])
            payload = curve_example['payload']
            protected_header = curve_example['protected_header']
            jws_test = jws.JWS(payload)
            jws_test.add_signature(key, None,
                                   json_encode(protected_header), None)
            jws_test_serialization_compact = \
                jws_test.serialize(compact=True)
            self.assertEqual(jws_test_serialization_compact,
                             curve_example['jws_serialization_compact'])
            jws_verify = jws.JWS()
            jws_verify.deserialize(jws_test_serialization_compact)
            jws_verify.verify(key.public())
            self.assertEqual(jws_verify.payload.decode('utf-8'),
                             curve_example['payload'])

    def test_secp256k1_signing_and_verification(self):
        key = jwk.JWK(**PrivateKeys_secp256k1['keys'][0])
        payload = bytes(bytearray(A1_payload))
        jws_test = jws.JWS(payload)
        jws_test.add_signature(key, None, json_encode({"alg": "ES256K"}), None)
        jws_test_serialization_compact = jws_test.serialize(compact=True)
        jws_verify = jws.JWS()
        jws_verify.deserialize(jws_test_serialization_compact)
        jws_verify.verify(key.public())
        self.assertEqual(jws_verify.payload, payload)

    def test_brainpool_signing_and_verification(self):
        for key_data in PrivateKeys_brainpool['keys']:
            key = jwk.JWK(**key_data)
            payload = bytes(bytearray(A1_payload))
            jws_test = jws.JWS(payload)

            curve_name = key.get('crv')
            if curve_name == "BP-256":
                alg = "BP256R1"
            elif curve_name == "BP-384":
                alg = "BP384R1"
            else:
                alg = "BP512R1"

            jws_test.allowed_algs = [alg]
            jws_test.add_signature(key, None, json_encode({"alg": alg}), None)
            jws_test_serialization_compact = jws_test.serialize(compact=True)

            jws_verify = jws.JWS()
            jws_verify.allowed_algs = [alg]
            jws_verify.deserialize(jws_test_serialization_compact)
            jws_verify.verify(key.public())

            self.assertEqual(jws_verify.payload, payload)

    def test_jws_issue_224(self):
        key = jwk.JWK().generate(kty='oct')

        # Test Empty payload is supported for creating and verifying signatures
        s = jws.JWS(payload='')
        s.add_signature(key, None, json_encode({"alg": "HS256"}))
        o1 = s.serialize(compact=True)
        self.assertTrue('..' in o1)
        o2 = json_decode(s.serialize())
        self.assertEqual(o2['payload'], '')

        t = jws.JWS()
        t.deserialize(o1)
        t.verify(key)

    def test_jws_issue_281(self):
        header = {"alg": "HS256"}
        header_copy = copy.deepcopy(header)

        key = jwk.JWK().generate(kty='oct')

        s = jws.JWS(payload='test')
        s.add_signature(key, protected=header,
                        header={"kid": key.thumbprint()})

        self.assertEqual(header, header_copy)

    def test_decrypt_keyset(self):
        ks = jwk.JWKSet()
        key1 = jwk.JWK.generate(kty='oct', alg='HS256', kid='key1')
        key2 = jwk.JWK.generate(kty='oct', alg='HS384', kid='key2')
        key3 = jwk.JWK.generate(kty='oct', alg='HS512', kid='key3')
        ks.add(key1)
        ks.add(key2)
        s1 = jws.JWS(payload=b'secret')
        s1.add_signature(key1, protected='{"alg":"HS256"}')
        s2 = jws.JWS()
        s2.deserialize(s1.serialize(), ks)
        self.assertEqual(s2.payload, b'secret')

        s3 = jws.JWS(payload=b'secret')
        s3.add_signature(key3, protected='{"alg":"HS256"}')
        s4 = jws.JWS()
        with self.assertRaises(JWKeyNotFound):
            s4.deserialize(s3.serialize(), ks)


E_A1_plaintext = \
    [84, 104, 101, 32, 116, 114, 117, 101, 32, 115, 105, 103, 110, 32,
     111, 102, 32, 105, 110, 116, 101, 108, 108, 105, 103, 101, 110, 99,
     101, 32, 105, 115, 32, 110, 111, 116, 32, 107, 110, 111, 119, 108,
     101, 100, 103, 101, 32, 98, 117, 116, 32, 105, 109, 97, 103, 105,
     110, 97, 116, 105, 111, 110, 46]
E_A1_protected = "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkEyNTZHQ00ifQ"
E_A1_key = \
    {"kty": "RSA",
     "n": "oahUIoWw0K0usKNuOR6H4wkf4oBUXHTxRvgb48E-BVvxkeDNjbC4he8rUW"
          "cJoZmds2h7M70imEVhRU5djINXtqllXI4DFqcI1DgjT9LewND8MW2Krf3S"
          "psk_ZkoFnilakGygTwpZ3uesH-PFABNIUYpOiN15dsQRkgr0vEhxN92i2a"
          "sbOenSZeyaxziK72UwxrrKoExv6kc5twXTq4h-QChLOln0_mtUZwfsRaMS"
          "tPs6mS6XrgxnxbWhojf663tuEQueGC-FCMfra36C9knDFGzKsNa7LZK2dj"
          "YgyD3JR_MB_4NUJW_TqOQtwHYbxevoJArm-L5StowjzGy-_bq6Gw",
     "e": "AQAB",
     "d": "kLdtIj6GbDks_ApCSTYQtelcNttlKiOyPzMrXHeI-yk1F7-kpDxY4-WY5N"
          "WV5KntaEeXS1j82E375xxhWMHXyvjYecPT9fpwR_M9gV8n9Hrh2anTpTD9"
          "3Dt62ypW3yDsJzBnTnrYu1iwWRgBKrEYY46qAZIrA2xAwnm2X7uGR1hghk"
          "qDp0Vqj3kbSCz1XyfCs6_LehBwtxHIyh8Ripy40p24moOAbgxVw3rxT_vl"
          "t3UVe4WO3JkJOzlpUf-KTVI2Ptgm-dARxTEtE-id-4OJr0h-K-VFs3VSnd"
          "VTIznSxfyrj8ILL6MG_Uv8YAu7VILSB3lOW085-4qE3DzgrTjgyQ",
     "p": "1r52Xk46c-LsfB5P442p7atdPUrxQSy4mti_tZI3Mgf2EuFVbUoDBvaRQ-"
          "SWxkbkmoEzL7JXroSBjSrK3YIQgYdMgyAEPTPjXv_hI2_1eTSPVZfzL0lf"
          "fNn03IXqWF5MDFuoUYE0hzb2vhrlN_rKrbfDIwUbTrjjgieRbwC6Cl0",
     "q": "wLb35x7hmQWZsWJmB_vle87ihgZ19S8lBEROLIsZG4ayZVe9Hi9gDVCOBm"
          "UDdaDYVTSNx_8Fyw1YYa9XGrGnDew00J28cRUoeBB_jKI1oma0Orv1T9aX"
          "IWxKwd4gvxFImOWr3QRL9KEBRzk2RatUBnmDZJTIAfwTs0g68UZHvtc",
     "dp": "ZK-YwE7diUh0qR1tR7w8WHtolDx3MZ_OTowiFvgfeQ3SiresXjm9gZ5KL"
           "hMXvo-uz-KUJWDxS5pFQ_M0evdo1dKiRTjVw_x4NyqyXPM5nULPkcpU827"
           "rnpZzAJKpdhWAgqrXGKAECQH0Xt4taznjnd_zVpAmZZq60WPMBMfKcuE",
     "dq": "Dq0gfgJ1DdFGXiLvQEZnuKEN0UUmsJBxkjydc3j4ZYdBiMRAy86x0vHCj"
           "ywcMlYYg4yoC4YZa9hNVcsjqA3FeiL19rk8g6Qn29Tt0cj8qqyFpz9vNDB"
           "UfCAiJVeESOjJDZPYHdHY8v1b-o-Z2X5tvLx-TCekf7oxyeKDUqKWjis",
     "qi": "VIMpMYbPf47dT1w_zDUXfPimsSegnMOA1zTaX7aGk_8urY6R8-ZW1FxU7"
           "AlWAyLWybqq6t16VFd7hQd0y6flUK4SlOydB61gwanOsXGOAOv82cHq0E3"
           "eL4HrtZkUuKvnPrMnsUUFlfUdybVzxyjz9JF_XyaY14ardLSjf4L_FNY"}
E_A1_vector = \
    "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkEyNTZHQ00ifQ." \
    "OKOawDo13gRp2ojaHV7LFpZcgV7T6DVZKTyKOMTYUmKoTCVJRgckCL9kiMT03JGe" \
    "ipsEdY3mx_etLbbWSrFr05kLzcSr4qKAq7YN7e9jwQRb23nfa6c9d-StnImGyFDb" \
    "Sv04uVuxIp5Zms1gNxKKK2Da14B8S4rzVRltdYwam_lDp5XnZAYpQdb76FdIKLaV" \
    "mqgfwX7XWRxv2322i-vDxRfqNzo_tETKzpVLzfiwQyeyPGLBIO56YJ7eObdv0je8" \
    "1860ppamavo35UgoRdbYaBcoh9QcfylQr66oc6vFWXRcZ_ZT2LawVCWTIy3brGPi" \
    "6UklfCpIMfIjf7iGdXKHzg." \
    "48V1_ALb6US04U3b." \
    "5eym8TW_c8SuK0ltJ3rpYIzOeDQz7TALvtu6UG9oMo4vpzs9tX_EFShS8iB7j6ji" \
    "SdiwkIr3ajwQzaBtQD_A." \
    "XFBoMYUZodetZdvTiFvSkQ"

E_A1_ex = {'key': jwk.JWK(**E_A1_key),
           'protected': base64url_decode(E_A1_protected),
           'plaintext': bytes(bytearray(E_A1_plaintext)),
           'vector': E_A1_vector}

E_A2_plaintext = "Live long and prosper."
E_A2_protected = "eyJhbGciOiJSU0ExXzUiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0"
E_A2_key = \
    {"kty": "RSA",
     "n": "sXchDaQebHnPiGvyDOAT4saGEUetSyo9MKLOoWFsueri23bOdgWp4Dy1Wl"
          "UzewbgBHod5pcM9H95GQRV3JDXboIRROSBigeC5yjU1hGzHHyXss8UDpre"
          "cbAYxknTcQkhslANGRUZmdTOQ5qTRsLAt6BTYuyvVRdhS8exSZEy_c4gs_"
          "7svlJJQ4H9_NxsiIoLwAEk7-Q3UXERGYw_75IDrGA84-lA_-Ct4eTlXHBI"
          "Y2EaV7t7LjJaynVJCpkv4LKjTTAumiGUIuQhrNhZLuF_RJLqHpM2kgWFLU"
          "7-VTdL1VbC2tejvcI2BlMkEpk1BzBZI0KQB0GaDWFLN-aEAw3vRw",
     "e": "AQAB",
     "d": "VFCWOqXr8nvZNyaaJLXdnNPXZKRaWCjkU5Q2egQQpTBMwhprMzWzpR8Sxq"
          "1OPThh_J6MUD8Z35wky9b8eEO0pwNS8xlh1lOFRRBoNqDIKVOku0aZb-ry"
          "nq8cxjDTLZQ6Fz7jSjR1Klop-YKaUHc9GsEofQqYruPhzSA-QgajZGPbE_"
          "0ZaVDJHfyd7UUBUKunFMScbflYAAOYJqVIVwaYR5zWEEceUjNnTNo_CVSj"
          "-VvXLO5VZfCUAVLgW4dpf1SrtZjSt34YLsRarSb127reG_DUwg9Ch-Kyvj"
          "T1SkHgUWRVGcyly7uvVGRSDwsXypdrNinPA4jlhoNdizK2zF2CWQ",
     "p": "9gY2w6I6S6L0juEKsbeDAwpd9WMfgqFoeA9vEyEUuk4kLwBKcoe1x4HG68"
          "ik918hdDSE9vDQSccA3xXHOAFOPJ8R9EeIAbTi1VwBYnbTp87X-xcPWlEP"
          "krdoUKW60tgs1aNd_Nnc9LEVVPMS390zbFxt8TN_biaBgelNgbC95sM",
     "q": "uKlCKvKv_ZJMVcdIs5vVSU_6cPtYI1ljWytExV_skstvRSNi9r66jdd9-y"
          "BhVfuG4shsp2j7rGnIio901RBeHo6TPKWVVykPu1iYhQXw1jIABfw-MVsN"
          "-3bQ76WLdt2SDxsHs7q7zPyUyHXmps7ycZ5c72wGkUwNOjYelmkiNS0",
     "dp": "w0kZbV63cVRvVX6yk3C8cMxo2qCM4Y8nsq1lmMSYhG4EcL6FWbX5h9yuv"
           "ngs4iLEFk6eALoUS4vIWEwcL4txw9LsWH_zKI-hwoReoP77cOdSL4AVcra"
           "Hawlkpyd2TWjE5evgbhWtOxnZee3cXJBkAi64Ik6jZxbvk-RR3pEhnCs",
     "dq": "o_8V14SezckO6CNLKs_btPdFiO9_kC1DsuUTd2LAfIIVeMZ7jn1Gus_Ff"
           "7B7IVx3p5KuBGOVF8L-qifLb6nQnLysgHDh132NDioZkhH7mI7hPG-PYE_"
           "odApKdnqECHWw0J-F0JWnUd6D2B_1TvF9mXA2Qx-iGYn8OVV1Bsmp6qU",
     "qi": "eNho5yRBEBxhGBtQRww9QirZsB66TrfFReG_CcteI1aCneT0ELGhYlRlC"
           "tUkTRclIfuEPmNsNDPbLoLqqCVznFbvdB7x-Tl-m0l_eFTj2KiqwGqE9PZ"
           "B9nNTwMVvH3VRRSLWACvPnSiwP8N5Usy-WRXS-V7TbpxIhvepTfE0NNo"}
E_A2_vector = \
    "eyJhbGciOiJSU0ExXzUiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0." \
    "UGhIOguC7IuEvf_NPVaXsGMoLOmwvc1GyqlIKOK1nN94nHPoltGRhWhw7Zx0-kFm" \
    "1NJn8LE9XShH59_i8J0PH5ZZyNfGy2xGdULU7sHNF6Gp2vPLgNZ__deLKxGHZ7Pc" \
    "HALUzoOegEI-8E66jX2E4zyJKx-YxzZIItRzC5hlRirb6Y5Cl_p-ko3YvkkysZIF" \
    "NPccxRU7qve1WYPxqbb2Yw8kZqa2rMWI5ng8OtvzlV7elprCbuPhcCdZ6XDP0_F8" \
    "rkXds2vE4X-ncOIM8hAYHHi29NX0mcKiRaD0-D-ljQTP-cFPgwCp6X-nZZd9OHBv" \
    "-B3oWh2TbqmScqXMR4gp_A." \
    "AxY8DCtDaGlsbGljb3RoZQ." \
    "KDlTtXchhZTGufMYmOYGS4HffxPSUrfmqCHXaI9wOGY." \
    "9hH0vgRfYgPnAHOd8stkvw"

E_A2_ex = {'key': jwk.JWK(**E_A2_key),
           'protected': base64url_decode(E_A2_protected),
           'plaintext': E_A2_plaintext,
           'vector': E_A2_vector}

E_A3_plaintext = "Live long and prosper."
E_A3_protected = "eyJhbGciOiJBMTI4S1ciLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0"
E_A3_key = {"kty": "oct", "k": "GawgguFyGrWKav7AX4VKUg"}
E_A3_vector = \
    "eyJhbGciOiJBMTI4S1ciLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0." \
    "6KB707dM9YTIgHtLvtgWQ8mKwboJW3of9locizkDTHzBC2IlrT1oOQ." \
    "AxY8DCtDaGlsbGljb3RoZQ." \
    "KDlTtXchhZTGufMYmOYGS4HffxPSUrfmqCHXaI9wOGY." \
    "U0m_YmjN04DJvceFICbCVQ"

E_A3_ex = {'key': jwk.JWK(**E_A3_key),
           'protected': base64url_decode(E_A3_protected).decode('utf-8'),
           'plaintext': E_A3_plaintext,
           'vector': E_A3_vector}

E_A4_protected = "eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0"
E_A4_unprotected = {"jku": "https://server.example.com/keys.jwks"}
E_A4_vector = \
    '{"protected":"eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0",' \
    '"unprotected":{"jku":"https://server.example.com/keys.jwks"},' \
    '"recipients":[' \
    '{"header":{"alg":"RSA1_5","kid":"2011-04-29"},' \
    '"encrypted_key":'\
    '"UGhIOguC7IuEvf_NPVaXsGMoLOmwvc1GyqlIKOK1nN94nHPoltGRhWhw7Zx0-' \
    'kFm1NJn8LE9XShH59_i8J0PH5ZZyNfGy2xGdULU7sHNF6Gp2vPLgNZ__deLKx' \
    'GHZ7PcHALUzoOegEI-8E66jX2E4zyJKx-YxzZIItRzC5hlRirb6Y5Cl_p-ko3' \
    'YvkkysZIFNPccxRU7qve1WYPxqbb2Yw8kZqa2rMWI5ng8OtvzlV7elprCbuPh' \
    'cCdZ6XDP0_F8rkXds2vE4X-ncOIM8hAYHHi29NX0mcKiRaD0-D-ljQTP-cFPg' \
    'wCp6X-nZZd9OHBv-B3oWh2TbqmScqXMR4gp_A"},' \
    '{"header":{"alg":"A128KW","kid":"7"},' \
    '"encrypted_key":' \
    '"6KB707dM9YTIgHtLvtgWQ8mKwboJW3of9locizkDTHzBC2IlrT1oOQ"}],' \
    '"iv":"AxY8DCtDaGlsbGljb3RoZQ",' \
    '"ciphertext":"KDlTtXchhZTGufMYmOYGS4HffxPSUrfmqCHXaI9wOGY",' \
    '"tag":"Mz-VPPyU4RlcuYv1IwIvzw"}'

E_A4_ex = {'key1': jwk.JWK(**E_A2_key),
           'header1': '{"alg":"RSA1_5","kid":"2011-04-29"}',
           'key2': jwk.JWK(**E_A3_key),
           'header2': '{"alg":"A128KW","kid":"7"}',
           'protected': base64url_decode(E_A4_protected),
           'unprotected': json_encode(E_A4_unprotected),
           'plaintext': E_A3_plaintext,
           'vector': E_A4_vector}

E_A5_ex = \
    '{"protected":"eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0",' \
    '"unprotected":{"jku":"https://server.example.com/keys.jwks"},' \
    '"header":{"alg":"A128KW","kid":"7"},' \
    '"encrypted_key":' \
    '"6KB707dM9YTIgHtLvtgWQ8mKwboJW3of9locizkDTHzBC2IlrT1oOQ",' \
    '"iv":"AxY8DCtDaGlsbGljb3RoZQ",' \
    '"ciphertext":"KDlTtXchhZTGufMYmOYGS4HffxPSUrfmqCHXaI9wOGY",' \
    '"tag":"Mz-VPPyU4RlcuYv1IwIvzw"}'

customhdr_jwe_ex = \
    '{"protected":"eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0",' \
    '"unprotected":{"jku":"https://server.example.com/keys.jwks"},' \
    '"header":{"alg":"A128KW","kid":"7", "custom1":"custom_val"},' \
    '"encrypted_key":' \
    '"6KB707dM9YTIgHtLvtgWQ8mKwboJW3of9locizkDTHzBC2IlrT1oOQ",' \
    '"iv":"AxY8DCtDaGlsbGljb3RoZQ",' \
    '"ciphertext":"KDlTtXchhZTGufMYmOYGS4HffxPSUrfmqCHXaI9wOGY",' \
    '"tag":"Mz-VPPyU4RlcuYv1IwIvzw"}'

Issue_136_Protected_Header_no_epk = {
    "alg": "ECDH-ES+A256KW",
    "enc": "A256CBC-HS512"}

Issue_136_Contributed_JWE = \
    "eyJhbGciOiJFQ0RILUVTK0ExMjhLVyIsImVuYyI6IkEyNTZDQkMtSFM1MTIiLCJr" \
    "aWQiOiJrZXkxIiwiZXBrIjp7Imt0eSI6IkVDIiwiY3J2IjoiUC0yNTYiLCJ4Ijoi" \
    "cDNpU241cEFSNUpYUE5aVF9SSEw2MTJMUGliWEI2WDhvTE9EOXFrN2NhTSIsInki" \
    "OiI1Y04yQ2FqeXM3SVlDSXFEby1QUHF2bVQ1RzFvMEEtU0JicEQ5NFBOb3NNIn19" \
    ".wG51hYE_Vma8tvFKVyeZs4lsHhXiarEw3-59eWHPmhRflDAKrMvnBw1urezo_Bz" \
    "ZyPJ76m42ORQPbhEu5NvbJk3vgdgcp03j" \
    ".lRttW8r6P6zM0uYDQt0EjQ.qnOnz7biCbqdLEdUH3acMamFm-cBRCSTFb83tNPrgDU" \
    ".vZnwYpYjzrTaYritwMzaguaAMsq9rQOWe8NUHICv2hg"

Issue_136_Contributed_Key = {
    "alg": "ECDH-ES+A128KW",
    "crv": "P-256",
    "d": "F2PnliYin65AoIUxL1CwwzBPNeL2TyZPAKtkXOP50l8",
    "kid": "key1",
    "kty": "EC",
    "x": "FPrb_xwxe8SBP3kO-e-WsofFp7n5-yc_tGgfAvqAP8g",
    "y": "lM3HuyKMYUVsYdGqiWlkwTZbGO3Fh-hyadq8lfkTgBc"}

# RFC 8037 A.1
E_Ed25519 = {
    'key_json': '{"kty": "OKP",'
                '"crv": "Ed25519", '
                '"d": "nWGxne_9WmC6hEr0kuwsxERJxWl7MmkZcDusAxyuf2A", '
                '"x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"}',
    'payload': 'Example of Ed25519 signing',
    'protected_header': {"alg": "EdDSA"},
    'jws_serialization_compact': 'eyJhbGciOiJFZERTQSJ9.RXhhbXBsZSBvZiBF'
                                 'ZDI1NTE5IHNpZ25pbmc.hgyY0il_MGCjP0Jzl'
                                 'nLWG1PPOt7-09PGcvMg3AIbQR6dWbhijcNR4ki'
                                 '4iylGjg5BhVsPt9g7sVvpAr_MuM0KAg'}

X25519_Protected_Header_no_epk = {
    "alg": "ECDH-ES+A128KW",
    "enc": "A128GCM"}


class TestJWE(unittest.TestCase):
    def check_enc(self, plaintext, protected, key, vector):
        e = jwe.JWE(plaintext, protected, algs=jwe_algs_and_rsa1_5)
        e.add_recipient(key)
        # Encrypt and serialize using compact
        enc = e.serialize()
        # And test that we can decrypt our own
        e.deserialize(enc, key)
        # Now test the Spec Test Vector
        e.deserialize(vector, key)

    def test_A1(self):
        self.check_enc(E_A1_ex['plaintext'], E_A1_ex['protected'],
                       E_A1_ex['key'], E_A1_ex['vector'])

    def test_A2(self):
        self.check_enc(E_A2_ex['plaintext'], E_A2_ex['protected'],
                       E_A2_ex['key'], E_A2_ex['vector'])

    def test_A3(self):
        self.check_enc(E_A3_ex['plaintext'], E_A3_ex['protected'],
                       E_A3_ex['key'], E_A3_ex['vector'])

    def test_A4(self):
        e = jwe.JWE(E_A4_ex['plaintext'], E_A4_ex['protected'],
                    algs=jwe_algs_and_rsa1_5)
        e.add_recipient(E_A4_ex['key1'], E_A4_ex['header1'])
        e.add_recipient(E_A4_ex['key2'], E_A4_ex['header2'])
        enc = e.serialize()
        e.deserialize(enc, E_A4_ex['key1'])
        e.deserialize(enc, E_A4_ex['key2'])
        # Now test the Spec Test Vector
        e.deserialize(E_A4_ex['vector'], E_A4_ex['key1'])
        e.deserialize(E_A4_ex['vector'], E_A4_ex['key2'])

    def test_A5(self):
        e = jwe.JWE(algs=jwe_algs_and_rsa1_5)
        e.deserialize(E_A5_ex, E_A4_ex['key2'])
        with self.assertRaises(jwe.InvalidJWEData):
            e = jwe.JWE(algs=['A256KW'])
            e.deserialize(E_A5_ex, E_A4_ex['key2'])

    def test_compact_protected_header(self):
        """Compact representation requires a protected header"""
        e = jwe.JWE(E_A1_ex['plaintext'])
        e.add_recipient(E_A1_ex['key'], E_A1_ex['protected'])

        with self.assertRaises(jwe.InvalidJWEOperation):
            e.serialize(compact=True)

    def test_compact_invalid_header(self):
        with self.assertRaises(jwe.InvalidJWEOperation):
            e = jwe.JWE(E_A1_ex['plaintext'], E_A1_ex['protected'],
                        aad='XYZ', recipient=E_A1_ex['key'])
            e.serialize(compact=True)

        with self.assertRaises(jwe.InvalidJWEOperation):
            e = jwe.JWE(E_A1_ex['plaintext'], E_A1_ex['protected'],
                        unprotected='{"jku":"https://example.com/keys.jwks"}',
                        recipient=E_A1_ex['key'])
            e.serialize(compact=True)

    def test_JWE_Issue_136(self):
        plaintext = "plain"
        protected = json_encode(Issue_136_Protected_Header_no_epk)
        key = jwk.JWK.generate(kty='EC', crv='P-521')
        e = jwe.JWE(plaintext, protected)
        e.add_recipient(key)
        enc = e.serialize()
        e.deserialize(enc, key)
        self.assertEqual(e.payload, plaintext.encode('utf-8'))

        e = jwe.JWE()
        e.deserialize(Issue_136_Contributed_JWE,
                      jwk.JWK(**Issue_136_Contributed_Key))

    def test_customhdr_jwe(self):
        def jwe_chk1(jwobj):
            return jwobj.jose_header['custom1'] == 'custom_val'

        newhdr = JWSEHeaderParameter('Custom header 1', False, True, jwe_chk1)
        newreg = {'custom1': newhdr}
        e = jwe.JWE(header_registry=newreg)
        e.deserialize(customhdr_jwe_ex, E_A4_ex['key2'])

        def jwe_chk2(jwobj):
            return jwobj.jose_header['custom1'] == 'custom_not'

        newhdr = JWSEHeaderParameter('Custom header 1', False, True, jwe_chk2)
        newreg = {'custom1': newhdr}
        e = jwe.JWE(header_registry=newreg)
        with self.assertRaises(jwe.InvalidJWEData):
            e.deserialize(customhdr_jwe_ex, E_A4_ex['key2'])

    def test_customhdr_jwe_exists(self):
        newhdr = JWSEHeaderParameter('Custom header 1', False, True, None)
        newreg = {'alg': newhdr}
        with self.assertRaises(InvalidJWSERegOperation):
            jwe.JWE(header_registry=newreg)

    def test_X25519_ECDH(self):
        plaintext = b"plain"
        protected = json_encode(X25519_Protected_Header_no_epk)
        if 'X25519' in jwk.ImplementedOkpCurves:
            x25519key = jwk.JWK.generate(kty='OKP', crv='X25519')
            e1 = jwe.JWE(plaintext, protected)
            e1.add_recipient(x25519key)
            enc = e1.serialize()
            e2 = jwe.JWE()
            e2.deserialize(enc, x25519key)
            self.assertEqual(e2.payload, plaintext)

    def test_decrypt_keyset(self):
        ks = jwk.JWKSet()
        key1 = jwk.JWK.generate(kty='oct', alg='A128KW', kid='key1')
        key2 = jwk.JWK.generate(kty='oct', alg='A192KW', kid='key2')
        key3 = jwk.JWK.generate(kty='oct', alg='A256KW', kid='key3')
        ks.add(key1)
        ks.add(key2)
        e1 = jwe.JWE(plaintext=b'secret')
        e1.add_recipient(key1, '{"alg":"A128KW","enc":"A128GCM"}')
        e2 = jwe.JWE()
        e2.deserialize(e1.serialize(), ks)
        self.assertEqual(e2.payload, b'secret')

        e3 = jwe.JWE(plaintext=b'secret')
        e3.add_recipient(key3, '{"alg":"A256KW","enc":"A256GCM"}')
        e4 = jwe.JWE()
        with self.assertRaises(JWKeyNotFound):
            e4.deserialize(e3.serialize(), ks)


MMA_vector_key = jwk.JWK(**E_A2_key)
MMA_vector_ok_cek =  \
    '{"protected":"eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0",' \
    '"unprotected":{"jku":"https://server.example.com/keys.jwks"},' \
    '"recipients":[' \
    '{"header":{"alg":"RSA1_5","kid":"2011-04-29"},' \
    '"encrypted_key":'\
    '"UGhIOguC7IuEvf_NPVaXsGMoLOmwvc1GyqlIKOK1nN94nHPoltGRhWhw7Zx0-' \
    'kFm1NJn8LE9XShH59_i8J0PH5ZZyNfGy2xGdULU7sHNF6Gp2vPLgNZ__deLKx' \
    'GHZ7PcHALUzoOegEI-8E66jX2E4zyJKx-YxzZIItRzC5hlRirb6Y5Cl_p-ko3' \
    'YvkkysZIFNPccxRU7qve1WYPxqbb2Yw8kZqa2rMWI5ng8OtvzlV7elprCbuPh' \
    'cCdZ6XDP0_F8rkXds2vE4X-ncOIM8hAYHHi29NX0mcKiRaD0-D-ljQTP-cFPg' \
    'wCp6X-nZZd9OHBv-B3oWh2TbqmScqXMR4gp_A"}],' \
    '"iv":"AxY8DCtDaGlsbGljb3RoZQ",' \
    '"ciphertext":"PURPOSEFULLYBROKENYGS4HffxPSUrfmqCHXaI9wOGY",' \
    '"tag":"Mz-VPPyU4RlcuYv1IwIvzw"}'
MMA_vector_ko_cek = \
    '{"protected":"eyJlbmMiOiJBMTI4Q0JDLUhTMjU2In0",' \
    '"unprotected":{"jku":"https://server.example.com/keys.jwks"},' \
    '"recipients":[' \
    '{"header":{"alg":"RSA1_5","kid":"2011-04-29"},' \
    '"encrypted_key":'\
    '"UGhIOguC7IuEvf_NPVaYsGMoLOmwvc1GyqlIKOK1nN94nHPoltGRhWhw7Zx0-' \
    'kFm1NJn8LE9XShH59_i8J0PH5ZZyNfGy2xGdULU7sHNF6Gp2vPLgNZ__deLKx' \
    'GHZ7PcHALUzoOegEI-8E66jX2E4zyJKx-YxzZIItRzC5hlRirb6Y5Cl_p-ko3' \
    'YvkkysZIFNPccxRU7qve1WYPxqbb2Yw8kZqa2rMWI5ng8OtvzlV7elprCbuPh' \
    'cCdZ6XDP0_F8rkXds2vE4X-ncOIM8hAYHHi29NX0mcKiRaD0-D-ljQTP-cFPg' \
    'wCp6X-nZZd9OHBv-B3oWh2TbqmScqXMR4gp_A"}],' \
    '"iv":"AxY8DCtDaGlsbGljb3RoZQ",' \
    '"ciphertext":"PURPOSEFULLYBROKENYGS4HffxPSUrfmqCHXaI9wOGY",' \
    '"tag":"Mz-VPPyU4RlcuYv1IwIvzw"}'


class TestMMA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls.enableMMA = os.environ.get('JWCRYPTO_TESTS_ENABLE_MMA', False)
        cls.iterations = 500
        cls.sub_iterations = 100

    def test_MMA(self):
        if self.enableMMA:

            print('Testing MMA timing attacks')

            ok_cek = 0
            ok_e = jwe.JWE(algs=jwe_algs_and_rsa1_5)
            ok_e.deserialize(MMA_vector_ok_cek)
            ko_cek = 0
            ko_e = jwe.JWE(algs=jwe_algs_and_rsa1_5)
            ko_e.deserialize(MMA_vector_ko_cek)

            import time
            counter = getattr(time, 'perf_counter', time.time)

            for _ in range(self.iterations):
                start = counter()
                for _ in range(self.sub_iterations):
                    with self.assertRaises(jwe.InvalidJWEData):
                        ok_e.decrypt(MMA_vector_key)
                stop = counter()
                ok_cek += (stop - start) / self.sub_iterations

                start = counter()
                for _ in range(self.sub_iterations):
                    with self.assertRaises(jwe.InvalidJWEData):
                        ko_e.decrypt(MMA_vector_key)
                stop = counter()
                ko_cek += (stop - start) / self.sub_iterations

            ok_cek /= self.iterations
            ko_cek /= self.iterations

            deviation = ((ok_cek - ko_cek) / ok_cek) * 100
            print('MMA ok cek: {}'.format(ok_cek))
            print('MMA ko cek: {}'.format(ko_cek))
            print('MMA deviation: {}% ({})'.format(int(deviation), deviation))
            self.assertLess(deviation, 2)


# RFC 7519
A1_header = {
    "alg": "RSA1_5",
    "enc": "A128CBC-HS256"}

A1_claims = {
    "iss": "joe",
    "exp": 1300819380,
    "http://example.com/is_root": True}

A1_token = \
    "eyJhbGciOiJSU0ExXzUiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2In0." + \
    "QR1Owv2ug2WyPBnbQrRARTeEk9kDO2w8qDcjiHnSJflSdv1iNqhWXaKH4MqAkQtM" + \
    "oNfABIPJaZm0HaA415sv3aeuBWnD8J-Ui7Ah6cWafs3ZwwFKDFUUsWHSK-IPKxLG" + \
    "TkND09XyjORj_CHAgOPJ-Sd8ONQRnJvWn_hXV1BNMHzUjPyYwEsRhDhzjAD26ima" + \
    "sOTsgruobpYGoQcXUwFDn7moXPRfDE8-NoQX7N7ZYMmpUDkR-Cx9obNGwJQ3nM52" + \
    "YCitxoQVPzjbl7WBuB7AohdBoZOdZ24WlN1lVIeh8v1K4krB8xgKvRU8kgFrEn_a" + \
    "1rZgN5TiysnmzTROF869lQ." + \
    "AxY8DCtDaGlsbGljb3RoZQ." + \
    "MKOle7UQrG6nSxTLX6Mqwt0orbHvAKeWnDYvpIAeZ72deHxz3roJDXQyhxx0wKaM" + \
    "HDjUEOKIwrtkHthpqEanSBNYHZgmNOV7sln1Eu9g3J8." + \
    "fiK51VwhsxJ-siBMR-YFiA"

A2_token = \
    "eyJhbGciOiJSU0ExXzUiLCJlbmMiOiJBMTI4Q0JDLUhTMjU2IiwiY3R5IjoiSldU" + \
    "In0." + \
    "g_hEwksO1Ax8Qn7HoN-BVeBoa8FXe0kpyk_XdcSmxvcM5_P296JXXtoHISr_DD_M" + \
    "qewaQSH4dZOQHoUgKLeFly-9RI11TG-_Ge1bZFazBPwKC5lJ6OLANLMd0QSL4fYE" + \
    "b9ERe-epKYE3xb2jfY1AltHqBO-PM6j23Guj2yDKnFv6WO72tteVzm_2n17SBFvh" + \
    "DuR9a2nHTE67pe0XGBUS_TK7ecA-iVq5COeVdJR4U4VZGGlxRGPLRHvolVLEHx6D" + \
    "YyLpw30Ay9R6d68YCLi9FYTq3hIXPK_-dmPlOUlKvPr1GgJzRoeC9G5qCvdcHWsq" + \
    "JGTO_z3Wfo5zsqwkxruxwA." + \
    "UmVkbW9uZCBXQSA5ODA1Mg." + \
    "VwHERHPvCNcHHpTjkoigx3_ExK0Qc71RMEParpatm0X_qpg-w8kozSjfNIPPXiTB" + \
    "BLXR65CIPkFqz4l1Ae9w_uowKiwyi9acgVztAi-pSL8GQSXnaamh9kX1mdh3M_TT" + \
    "-FZGQFQsFhu0Z72gJKGdfGE-OE7hS1zuBD5oEUfk0Dmb0VzWEzpxxiSSBbBAzP10" + \
    "l56pPfAtrjEYw-7ygeMkwBl6Z_mLS6w6xUgKlvW6ULmkV-uLC4FUiyKECK4e3WZY" + \
    "Kw1bpgIqGYsw2v_grHjszJZ-_I5uM-9RA8ycX9KqPRp9gc6pXmoU_-27ATs9XCvr" + \
    "ZXUtK2902AUzqpeEUJYjWWxSNsS-r1TJ1I-FMJ4XyAiGrfmo9hQPcNBYxPz3GQb2" + \
    "8Y5CLSQfNgKSGt0A4isp1hBUXBHAndgtcslt7ZoQJaKe_nNJgNliWtWpJ_ebuOpE" + \
    "l8jdhehdccnRMIwAmU1n7SPkmhIl1HlSOpvcvDfhUN5wuqU955vOBvfkBOh5A11U" + \
    "zBuo2WlgZ6hYi9-e3w29bR0C2-pp3jbqxEDw3iWaf2dc5b-LnR0FEYXvI_tYk5rd" + \
    "_J9N0mg0tQ6RbpxNEMNoA9QWk5lgdPvbh9BaO195abQ." + \
    "AVO9iT5AV4CzvDJCdhSFlQ"


class TestJWT(unittest.TestCase):

    def test_A1(self):
        key = jwk.JWK(**E_A2_key)
        # first encode/decode ourselves
        t = jwt.JWT(A1_header, A1_claims,
                    algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()
        t.deserialize(token)
        # then try the test vector
        t = jwt.JWT(jwt=A1_token, key=key, check_claims=False,
                    algs=jwe_algs_and_rsa1_5)
        # then try the test vector with explicit expiration date
        t = jwt.JWT(jwt=A1_token, key=key, check_claims={'exp': 1300819380},
                    algs=jwe_algs_and_rsa1_5)
        # Finally check it raises for expired tokens
        self.assertRaises(jwt.JWTExpired, jwt.JWT, jwt=A1_token, key=key,
                          algs=jwe_algs_and_rsa1_5)

    def test_A2(self):
        sigkey = jwk.JWK(**A2_example['key'])
        touter = jwt.JWT(jwt=A2_token, key=E_A2_ex['key'],
                         algs=jwe_algs_and_rsa1_5)
        tinner = jwt.JWT(jwt=touter.claims, key=sigkey, check_claims=False)
        self.assertEqual(A1_claims, json_decode(tinner.claims))

        # Test Exception throwing when token is encrypted with
        # algorithms not in the allowed set
        with self.assertRaises(jwe.InvalidJWEData):
            jwt.JWT(jwt=A2_token, key=E_A2_ex['key'],
                    algs=['A192KW', 'A192CBC-HS384', 'RSA1_5'])

    def test_decrypt_keyset(self):
        key = jwk.JWK(kid='testkey', **E_A2_key)
        keyset = jwk.JWKSet.from_json(json_encode(PrivateKeys))

        # encrypt a new JWT with kid
        header = copy.copy(A1_header)
        header['kid'] = 'testkey'
        t = jwt.JWT(header, A1_claims, algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()
        # try to decrypt without a matching key
        self.assertRaises(jwt.JWTMissingKey, jwt.JWT, jwt=token, key=keyset,
                          algs=jwe_algs_and_rsa1_5,
                          check_claims={'exp': 1300819380})
        # now decrypt with key
        keyset.add(key)
        jwt.JWT(jwt=token, key=keyset, algs=jwe_algs_and_rsa1_5,
                check_claims={'exp': 1300819380})

        # encrypt a new JWT with wrong kid
        header = copy.copy(A1_header)
        header['kid'] = '1'
        t = jwt.JWT(header, A1_claims, algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()
        self.assertRaises(jwt.JWTMissingKey, jwt.JWT, jwt=token, key=keyset,
                          algs=jwe_algs_and_rsa1_5)

        keyset = jwk.JWKSet.from_json(json_encode(PrivateKeys))
        # encrypt a new JWT with no kid
        header = copy.copy(A1_header)
        t = jwt.JWT(header, A1_claims, algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()
        # try to decrypt without a matching key
        self.assertRaises(jwt.JWTMissingKey, jwt.JWT, jwt=token, key=keyset,
                          algs=jwe_algs_and_rsa1_5,
                          check_claims={'exp': 1300819380})
        # now decrypt with key
        keyset.add(key)
        jwt.JWT(jwt=token, key=keyset, algs=jwe_algs_and_rsa1_5,
                check_claims={'exp': 1300819380})

    def test_decrypt_keyset_dup_kid(self):
        keyset = jwk.JWKSet.from_json(json_encode(PrivateKeys))
        # add wrong key with duplicate kid
        key = jwk.JWK(kid='testkey', **E_A3_key)
        keyset.add(key)

        # encrypt a new JWT with kid
        key = jwk.JWK(kid='testkey', **E_A2_key)
        header = copy.copy(A1_header)
        header['kid'] = 'testkey'
        t = jwt.JWT(header, A1_claims, algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()

        # try to decrypt without a matching key
        with self.assertRaises(jwt.JWTMissingKey):
            jwt.JWT(jwt=token, key=keyset, algs=jwe_algs_and_rsa1_5,
                    check_claims={'exp': 1300819380})

        # add right key
        keyset.add(key)

        # now decrypt with key
        jwt.JWT(jwt=token, key=keyset, algs=jwe_algs_and_rsa1_5,
                check_claims={'exp': 1300819380})

    def test_invalid_claim_type(self):
        key = jwk.JWK(**E_A2_key)
        claims = {"testclaim": "test"}
        claims.update(A1_claims)
        t = jwt.JWT(A1_header, claims, algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()

        # Wrong string
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, algs=jwe_algs_and_rsa1_5,
                          check_claims={"testclaim": "ijgi"})

        # Wrong type
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, algs=jwe_algs_and_rsa1_5,
                          check_claims={"testclaim": 123})

        # Correct
        jwt.JWT(jwt=token, key=key, algs=jwe_algs_and_rsa1_5,
                check_claims={"testclaim": "test"})

    def test_claim_params(self):
        key = jwk.JWK(**E_A2_key)
        default_claims = {"iss": "test", "exp": None}
        string_claims = '{"string_claim":"test"}'
        string_header = '{"alg":"RSA1_5","enc":"A128CBC-HS256"}'
        t = jwt.JWT(string_header, string_claims,
                    default_claims=default_claims,
                    algs=jwe_algs_and_rsa1_5)
        t.make_encrypted_token(key)
        token = t.serialize()

        # Check default_claims
        jwt.JWT(jwt=token, key=key, algs=jwe_algs_and_rsa1_5,
                check_claims={"iss": "test", "exp": None,
                              "string_claim": "test"})

    def test_claims_typ(self):
        key = jwk.JWK().generate(kty='oct')
        claims = '{"typ":"application/test"}'
        string_header = '{"alg":"HS256"}'
        t = jwt.JWT(string_header, claims)
        t.make_signed_token(key)
        token = t.serialize()

        # Same typ w/o application prefix
        jwt.JWT(jwt=token, key=key, check_claims={"typ": "test"})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, check_claims={"typ": "wrong"})

        # Same typ w/ application prefix
        jwt.JWT(jwt=token, key=key, check_claims={"typ": "application/test"})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, check_claims={"typ": "application/wrong"})

        # check that a '/' in the name makes it not be matched with
        # 'application/' prefix
        claims = '{"typ":"diffmime/test"}'
        t = jwt.JWT(string_header, claims)
        t.make_signed_token(key)
        token = t.serialize()
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, check_claims={"typ": "application/test"})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, jwt=token,
                          key=key, check_claims={"typ": "test"})

        # finally make sure it doesn't raise if not checked.
        jwt.JWT(jwt=token, key=key)

    def test_empty_claims(self):
        key = jwk.JWK().generate(kty='oct')

        # empty dict is valid
        t = jwt.JWT('{"alg":"HS256"}', {})
        self.assertEqual('{}', t.claims)
        t.make_signed_token(key)
        token = t.serialize()

        _jwt = jwt.JWT()
        _jwt.deserialize(token, key)
        self.assertEqual('{}', _jwt.claims)

        # empty string is also valid
        t = jwt.JWT('{"alg":"HS256"}', '')
        t.make_signed_token(key)
        token = t.serialize()

        # also a space is fine
        t = jwt.JWT('{"alg":"HS256"}', ' ')
        self.assertEqual(' ', t.claims)
        t.make_signed_token(key)
        token = t.serialize()

        _jwt = jwt.JWT()
        _jwt.deserialize(token, key)
        self.assertEqual(' ', _jwt.claims)

    def test_Issue_209(self):
        key = jwk.JWK(**A3_key)
        t = jwt.JWT('{"alg":"ES256"}', {})
        t.make_signed_token(key)
        token = t.serialize()

        ks = jwk.JWKSet()
        ks.add(jwk.JWK().generate(kty='oct'))
        ks.add(key)

        # Make sure this one does not assert when cycling through
        # the oct key before hitting the ES one
        jwt.JWT(jwt=token, key=ks)

    def test_Issue_277(self):
        claims = {"aud": ["www.example.com", "www.test.net"]}
        key = jwk.JWK(generate='oct', size=256)
        token = jwt.JWT(header={"alg": "HS256"}, claims=claims)
        token.make_signed_token(key)
        sertok = token.serialize()
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": "www.example.com"})
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": "www.test.net"})
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": ["www.example.com"]})
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": ["www.test.net"]})
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": ["www.example.com",
                                                           "www.test.net"]})
        jwt.JWT(key=key, jwt=sertok, check_claims={"aud": ["www.example.com",
                                                           "nomatch"]})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, key=key,
                          jwt=sertok, check_claims={"aud": "nomatch"})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, key=key,
                          jwt=sertok, check_claims={"aud": ["nomatch"]})
        self.assertRaises(jwt.JWTInvalidClaimValue, jwt.JWT, key=key,
                          jwt=sertok, check_claims={"aud": ["nomatch",
                                                            "failmatch"]})

    def test_unexpected(self):
        key = jwk.JWK(generate='oct', size=256)
        claims = {"testclaim": "test"}
        token = jwt.JWT(header={"alg": "HS256"}, claims=claims)
        token.make_signed_token(key)
        sertok = token.serialize()

        token.validate(key)
        token.expected_type = "JWS"
        token.validate(key)
        token.expected_type = "JWE"
        with self.assertRaises(TypeError):
            token.validate(key)

        jwt.JWT(jwt=sertok, key=key)
        jwt.JWT(jwt=sertok, key=key, expected_type='JWS')
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=sertok, key=key, expected_type='JWE')

        jwt.JWT(jwt=sertok, algs=['HS256'], key=key)

        key.use = 'sig'
        jwt.JWT(jwt=sertok, key=key)
        key.use = 'enc'
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=sertok, key=key)
        key.use = None
        key.key_ops = 'verify'
        jwt.JWT(jwt=sertok, key=key)
        key.key_ops = ['sign', 'verify']
        jwt.JWT(jwt=sertok, key=key)
        key.key_ops = 'decrypt'
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=sertok, key=key)
        key.key_ops = ['encrypt', 'decrypt']
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=sertok, key=key)
        key.key_ops = None

        token = jwt.JWT(header={"alg": "A256KW", "enc": "A256GCM"},
                        claims=claims)
        token.make_encrypted_token(key)
        enctok = token.serialize()

        # test workaround for older applications
        jwt.JWT_expect_type = False
        jwt.JWT(jwt=enctok, key=key)
        jwt.JWT_expect_type = True

        token.validate(key)
        token.expected_type = "JWE"
        token.validate(key)
        token.expected_type = "JWS"
        with self.assertRaises(TypeError):
            token.validate(key)

        jwt.JWT(jwt=enctok, key=key, expected_type='JWE')
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=enctok, key=key)
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=enctok, key=key, expected_type='JWS')

        jwt.JWT(jwt=enctok, algs=['A256KW', 'A256GCM'], key=key)

        key.use = 'enc'
        jwt.JWT(jwt=enctok, key=key)
        key.use = 'sig'
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=enctok, key=key)
        key.use = None
        key.key_ops = 'verify'
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=enctok, key=key)
        key.key_ops = ['sign', 'verify']
        with self.assertRaises(TypeError):
            jwt.JWT(jwt=enctok, key=key)
        key.key_ops = 'decrypt'
        jwt.JWT(jwt=enctok, key=key)
        key.key_ops = ['encrypt', 'decrypt']
        jwt.JWT(jwt=enctok, key=key)
        key.key_ops = None


class ConformanceTests(unittest.TestCase):

    def test_unknown_key_params(self):
        key = jwk.JWK(kty='oct', k='secret', unknown='mystery')
        self.assertEqual('mystery', key.get('unknown'))

    def test_key_ops_values(self):
        self.assertRaises(jwk.InvalidJWKValue, jwk.JWK,
                          kty='RSA', n=1, key_ops=['sign'], use='enc')
        self.assertRaises(jwk.InvalidJWKValue, jwk.JWK,
                          kty='RSA', n=1, key_ops=['sign', 'sign'])

    def test_jwe_no_protected_header(self):
        enc = jwe.JWE(plaintext='plain')
        enc.add_recipient(jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16)),
                          '{"alg":"A128KW","enc":"A128GCM"}')

    def test_jwe_no_alg_in_jose_headers(self):
        enc = jwe.JWE(plaintext='plain')
        self.assertRaises(jwe.InvalidJWEData, enc.add_recipient,
                          jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16)),
                          '{"enc":"A128GCM"}')

    def test_jwe_no_enc_in_jose_headers(self):
        enc = jwe.JWE(plaintext='plain')
        self.assertRaises(jwe.InvalidJWEData, enc.add_recipient,
                          jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16)),
                          '{"alg":"A128KW"}')

    def test_aes_128(self):
        enc = jwe.JWE(plaintext='plain')
        key128 = jwk.JWK(kty='oct', k=base64url_encode(b'A' * (128 // 8)))
        enc.add_recipient(key128, '{"alg":"A128KW","enc":"A128CBC-HS256"}')
        enc.add_recipient(key128, '{"alg":"A128KW","enc":"A128GCM"}')

    def test_aes_192(self):
        enc = jwe.JWE(plaintext='plain')
        key192 = jwk.JWK(kty='oct', k=base64url_encode(b'B' * (192 // 8)))
        enc.add_recipient(key192, '{"alg":"A192KW","enc":"A192CBC-HS384"}')
        enc.add_recipient(key192, '{"alg":"A192KW","enc":"A192GCM"}')

    def test_aes_256(self):
        enc = jwe.JWE(plaintext='plain')
        key256 = jwk.JWK(kty='oct', k=base64url_encode(b'C' * (256 // 8)))
        enc.add_recipient(key256, '{"alg":"A256KW","enc":"A256CBC-HS512"}')
        enc.add_recipient(key256, '{"alg":"A256KW","enc":"A256GCM"}')

    def test_jws_loopback(self):
        sign = jws.JWS(payload='message')
        sign.add_signature(jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16)),
                           alg="HS512")
        o = sign.serialize()
        check = jws.JWS()
        check.deserialize(o, jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16)),
                          alg="HS512")
        self.assertTrue(check.objects['valid'])

    def test_jws_headers_as_dicts(self):
        sign = jws.JWS(payload='message')
        key = jwk.JWK(kty='oct', k=base64url_encode(b'A' * 16))
        sign.add_signature(key, protected={'alg': 'HS512'},
                           header={'kid': key.thumbprint()})
        o = sign.serialize()
        check = jws.JWS()
        check.deserialize(o, key, alg="HS512")
        self.assertTrue(check.objects['valid'])
        self.assertEqual(check.jose_header['kid'], key.thumbprint())

    def test_jwe_headers_as_dicts(self):
        enc = jwe.JWE(plaintext='message',
                      protected={"alg": "A256KW", "enc": "A256CBC-HS512"})
        key = jwk.JWK(kty='oct', k=base64url_encode(b'A' * 32))
        enc.add_recipient(key, {'kid': key.thumbprint()})
        o = enc.serialize()
        check = jwe.JWE()
        check.deserialize(o)
        check.decrypt(key)
        self.assertEqual(check.payload, b'message')
        self.assertEqual(
            json_decode(check.objects['header'])['kid'], key.thumbprint())

    def test_jwe_default_recipient(self):
        key = jwk.JWK(kty='oct', k=base64url_encode(b'A' * (128 // 8)))
        enc = jwe.JWE(plaintext='plain',
                      protected='{"alg":"A128KW","enc":"A128GCM"}',
                      recipient=key).serialize()
        check = jwe.JWE()
        check.deserialize(enc, key)
        self.assertEqual(b'plain', check.payload)

    def test_none_key(self):
        e = "eyJhbGciOiJub25lIn0." + \
            "eyJpc3MiOiJqb2UiLCJodHRwOi8vZXhhbXBsZS5jb20vaXNfcm9vdCI6dHJ1ZX0."
        token = jwt.JWT(algs=['none'])
        k = jwk.JWK(generate='oct', size=0)
        token.deserialize(jwt=e, key=k)
        self.assertEqual(json_decode(token.claims),
                         {"iss": "joe", "http://example.com/is_root": True})
        with self.assertRaises(KeyError):
            token = jwt.JWT()
            token.deserialize(jwt=e)
            json_decode(token.claims)

    def test_no_default_rsa_1_5(self):
        s = jws.JWS('test')
        with self.assertRaisesRegex(jws.InvalidJWSOperation,
                                    'Algorithm not allowed'):
            s.add_signature(A2_key, alg="RSA1_5")

    def test_pbes2_hs256_aeskw(self):
        enc = jwe.JWE(plaintext='plain',
                      protected={"alg": "PBES2-HS256+A128KW",
                                 "enc": "A256CBC-HS512"})
        key = jwk.JWK.from_password('password')
        enc.add_recipient(key)
        o = enc.serialize()
        check = jwe.JWE()
        check.deserialize(o)
        check.decrypt(key)
        self.assertEqual(check.payload, b'plain')

    def test_pbes2_hs256_aeskw_custom_params(self):
        enc = jwe.JWE(plaintext='plain',
                      protected={"alg": "PBES2-HS256+A128KW",
                                 "enc": "A256CBC-HS512",
                                 "p2c": 4096,
                                 "p2s": base64url_encode("A" * 16)})
        key = jwk.JWK.from_password('password')
        enc.add_recipient(key)
        o = enc.serialize()
        check = jwe.JWE()
        check.deserialize(o)
        check.decrypt(key)
        self.assertEqual(check.payload, b'plain')

        enc = jwe.JWE(plaintext='plain',
                      protected={"alg": "PBES2-HS256+A128KW",
                                 "enc": "A256CBC-HS512",
                                 "p2c": 4096,
                                 "p2s": base64url_encode("A" * 7)})
        key = jwk.JWK.from_password('password')
        self.assertRaises(ValueError, enc.add_recipient, key)

        # Test p2c iteration checks
        maxiter = jwa.default_max_pbkdf2_iterations
        p2cenc = jwe.JWE(plaintext='plain',
                         protected={"alg": "PBES2-HS256+A128KW",
                                    "enc": "A256CBC-HS512",
                                    "p2c": maxiter + 1,
                                    "p2s": base64url_encode("A" * 16)})
        with self.assertRaisesRegex(ValueError, 'too large'):
            p2cenc.add_recipient(key)
        jwa.default_max_pbkdf2_iterations += 2
        p2cenc.add_recipient(key)

    def test_jwe_decompression_max(self):
        key = jwk.JWK(kty='oct', k=base64url_encode(b'A' * (128 // 8)))
        payload = '{"u": "' + "u" * 400000000 + '", "uu":"' \
            + "u" * 400000000 + '"}'
        protected_header = {
            "alg": "A128KW",
            "enc": "A128GCM",
            "typ": "JWE",
            "zip": "DEF",
        }
        enc = jwe.JWE(payload.encode('utf-8'),
                      recipient=key,
                      protected=protected_header).serialize(compact=True)
        with self.assertRaises(jwe.InvalidJWEData):
            check = jwe.JWE()
            check.deserialize(enc)
            check.decrypt(key)

        defmax = jwe.default_max_compressed_size
        jwe.default_max_compressed_size = 1000000000
        # ensure we can eraise the limit and decrypt
        check = jwe.JWE()
        check.deserialize(enc)
        check.decrypt(key)
        jwe.default_max_compressed_size = defmax


class JWATests(unittest.TestCase):
    def test_jwa_create(self):
        for name, cls in jwa.JWA.algorithms_registry.items():
            self.assertEqual(cls.name, name)
            self.assertIn(cls.algorithm_usage_location, {'alg', 'enc'})
            if name == 'ECDH-ES':
                self.assertIs(cls.keysize, None)
            elif name == 'EdDSA':
                self.assertIs(cls.keysize, None)
            else:
                self.assertIsInstance(cls.keysize, int)
                self.assertGreaterEqual(cls.keysize, 0)

            if cls.algorithm_use == 'sig':
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.encryption_alg(name)
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.keymgmt_alg(name)
                inst = jwa.JWA.signing_alg(name)
                self.assertIsInstance(inst, jwa.JWAAlgorithm)
                self.assertEqual(inst.name, name)
            elif cls.algorithm_use == 'kex':
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.encryption_alg(name)
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.signing_alg(name)
                inst = jwa.JWA.keymgmt_alg(name)
                self.assertIsInstance(inst, jwa.JWAAlgorithm)
                self.assertEqual(inst.name, name)
            elif cls.algorithm_use == 'enc':
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.signing_alg(name)
                with self.assertRaises(jwa.InvalidJWAAlgorithm):
                    jwa.JWA.keymgmt_alg(name)
                inst = jwa.JWA.encryption_alg(name)
                self.assertIsInstance(inst, jwa.JWAAlgorithm)
                self.assertEqual(inst.name, name)
            else:
                self.fail((name, cls))


# RFC 7797

rfc7797_e_header = '{"alg":"HS256"}'
rfc7797_u_header = '{"alg":"HS256","b64":false,"crit":["b64"]}'
rfc7797_payload = "$.02"


class TestUnencodedPayload(unittest.TestCase):

    def test_regular(self):
        result = \
            'eyJhbGciOiJIUzI1NiJ9.JC4wMg.' + \
            '5mvfOroL-g7HyqJoozehmsaqmvTYGEq5jTI1gVvoEoQ'

        s = jws.JWS(rfc7797_payload)
        s.add_signature(jwk.JWK(**SymmetricKeys['keys'][1]),
                        protected=rfc7797_e_header)
        sig = s.serialize(compact=True)
        self.assertEqual(sig, result)

    def test_compat_unencoded(self):
        result = \
            'eyJhbGciOiJIUzI1NiIsImI2NCI6ZmFsc2UsImNyaXQiOlsiYjY0Il19..' + \
            'A5dxf2s96_n5FLueVuW1Z_vh161FwXZC4YLPff6dmDY'

        s = jws.JWS(rfc7797_payload)
        s.add_signature(jwk.JWK(**SymmetricKeys['keys'][1]),
                        protected=rfc7797_u_header)
        # check unencoded payload is in serialized form
        sig = s.serialize()
        self.assertEqual(json_decode(sig)['payload'], rfc7797_payload)
        # check error raises if we try to get compact serialization
        with self.assertRaises(jws.InvalidJWSOperation):
            sig = s.serialize(compact=True)
        # check compact serialization is allowed with detached payload
        s.detach_payload()
        sig = s.serialize(compact=True)
        self.assertEqual(sig, result)

    def test_detached_payload_verification(self):
        token = \
            'eyJhbGciOiJIUzI1NiIsImI2NCI6ZmFsc2UsImNyaXQiOlsiYjY0Il19..' + \
            'A5dxf2s96_n5FLueVuW1Z_vh161FwXZC4YLPff6dmDY'

        s = jws.JWS()
        s.deserialize(token)
        s.verify(jwk.JWK(**SymmetricKeys['keys'][1]),
                 detached_payload=rfc7797_payload)
        self.assertTrue(s.is_valid)

    def test_misses_crit(self):
        s = jws.JWS(rfc7797_payload)
        with self.assertRaises(jws.InvalidJWSObject):
            s.add_signature(jwk.JWK(**SymmetricKeys['keys'][1]),
                            protected={"alg": "HS256", "b64": False})

    def test_mismatching_encoding(self):
        s = jws.JWS(rfc7797_payload)
        s.add_signature(jwk.JWK(**SymmetricKeys['keys'][0]),
                        protected=rfc7797_e_header)
        with self.assertRaises(jws.InvalidJWSObject):
            s.add_signature(jwk.JWK(**SymmetricKeys['keys'][1]),
                            protected=rfc7797_u_header)


class TestOverloadedOperators(unittest.TestCase):

    def test_jws_equality(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        payload = "My Integrity protected message"
        signer_a = jws.JWS(payload.encode('utf-8'))
        signer_b = jws.JWS(payload.encode('utf-8'))
        self.assertEqual(signer_a, signer_b)

        signer_a.add_signature(key, None,
                               json_encode({"alg": "HS256"}),
                               json_encode({"kid": key.thumbprint()}))
        # One is signed, the other is not
        self.assertNotEqual(signer_a, signer_b)

        signer_b.add_signature(key, None,
                               json_encode({"alg": "HS256"}),
                               json_encode({"kid": key.thumbprint()}))
        # This kind of signature is deterministic so they should be equal
        self.assertEqual(signer_a, signer_b)

        signer_c = jws.JWS.from_jose_token(signer_a.serialize())
        self.assertNotEqual(signer_a, signer_c)
        signer_c.verify(key)
        self.assertEqual(signer_a, signer_c)

    def test_jws_representations(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        payload = "My Integrity protected message"
        token = jws.JWS(payload.encode('utf-8'))
        self.assertEqual(str(token),
                         "JWS(payload=My Integrity protected message)")
        self.assertEqual(repr(token),
                         "JWS(payload=My Integrity protected message)")
        token.add_signature(key, None,
                            json_encode({"alg": "HS256"}),
                            json_encode({"kid": key.thumbprint()}))
        ser = token.serialize()
        self.assertEqual(str(token), ser)
        self.assertEqual(repr(token), f'JWS.from_json_token("{ser}")')

    def test_jwe_equality(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        payload = "My Encrypted message"
        signer_a = jwe.JWE(payload.encode('utf-8'),
                           json_encode({"alg": "A256KW",
                                        "enc": "A256CBC-HS512"}))
        signer_b = jwe.JWE(payload.encode('utf-8'),
                           json_encode({"alg": "A256KW",
                                        "enc": "A256CBC-HS512"}))
        self.assertEqual(signer_a, signer_b)

        signer_a.add_recipient(key)
        # One is encrypted, the other is not
        self.assertNotEqual(signer_a, signer_b)

        signer_b.add_recipient(key)
        # Encryption generates a random CEK so tokens will always differ
        self.assertNotEqual(signer_a, signer_b)

        signer_c = jwe.JWE.from_jose_token(signer_a.serialize())
        self.assertEqual(signer_a, signer_c)

    def test_jwe_representations(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        payload = "My Encrypted message"
        token = jwe.JWE(payload.encode('utf-8'),
                        json_encode({"alg": "A256KW",
                                     "enc": "A256CBC-HS512"}))
        strrep = "JWE(plaintext=b\'My Encrypted message\', " + \
                 "protected={\"alg\":\"A256KW\"," + \
                 "\"enc\":\"A256CBC-HS512\"}, " + \
                 "unprotected=None, aad=None, algs=None)"
        self.assertEqual(str(token), strrep)
        self.assertEqual(repr(token), strrep)

        token.add_recipient(key)
        ser = token.serialize()
        self.assertEqual(str(token), ser)
        self.assertEqual(repr(token), f'JWE.from_json_token("{ser}")')

    def test_jwt_equality(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        signer_a = jwt.JWT(header={"alg": "HS256"},
                           claims={"info": "I'm a signed token"})
        signer_b = jwt.JWT(header={"alg": "HS256"},
                           claims={"info": "I'm a signed token"})
        self.assertEqual(signer_a, signer_b)

        signer_a.make_signed_token(key)
        # One is signed, the other is not
        self.assertNotEqual(signer_a, signer_b)

        signer_b.make_signed_token(key)
        # This kind of signature is deterministic so they should be equal
        self.assertEqual(signer_a, signer_b)

        signer_c = jwt.JWT.from_jose_token(signer_a.serialize())
        self.assertNotEqual(signer_a, signer_c)
        signer_c.validate(key)
        self.assertEqual(signer_a, signer_c)

        ea = jwt.JWT(header={"alg": "A256KW", "enc": "A256CBC-HS512"},
                     claims=signer_a.serialize())
        eb = jwt.JWT(header={"alg": "A256KW", "enc": "A256CBC-HS512"},
                     claims=signer_b.serialize())
        self.assertEqual(ea, eb)

        ea.make_encrypted_token(key)
        # One is encrypted, the other is not
        self.assertNotEqual(ea, eb)

        eb.make_encrypted_token(key)
        # Encryption generates a random CEK so tokens will always differ
        self.assertNotEqual(ea, eb)

        ect = jwt.JWT.from_jose_token(ea.serialize())
        self.assertNotEqual(ea, ect)
        ect.expected_type = "JWE"
        ect.validate(key)
        self.assertEqual(ea, ect)

    def test_jwt_representations(self):
        key = jwk.JWK.generate(kty='oct', size=256)
        token = jwt.JWT(header={"alg": "HS256"},
                        claims={"info": "I'm a signed token"})
        strrep = 'JWT(header={"alg":"HS256"}, claims={"info":"I\'m a ' + \
                 'signed token"}, jwt=None, key=None, algs=None, ' + \
                 'default_claims=None, check_claims=None)'
        self.assertEqual(str(token), strrep)
        self.assertEqual(repr(token), strrep)
        token.make_signed_token(key)

        ser = token.serialize()
        self.assertEqual(str(token), ser)
        ser2 = token.token.serialize()

        reprrep = 'JWT(header={"alg":"HS256"}, ' + \
                  'claims={"info":"I\'m a signed token"}, ' + \
                  f'jwt=JWS.from_json_token("{ser2}"), key=None, ' + \
                  'algs=None, default_claims=None, check_claims=None)'
        self.assertEqual(repr(token), reprrep)
