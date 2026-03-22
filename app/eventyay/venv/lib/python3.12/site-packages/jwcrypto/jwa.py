# Copyright (C) 2016 JWCrypto Project Contributors - see LICENSE file

import os
import struct
from abc import ABCMeta, abstractmethod
from binascii import hexlify, unhexlify

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import constant_time, hashes, hmac
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import utils as ec_utils
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.concatkdf import ConcatKDFHash
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap, aes_key_wrap
from cryptography.hazmat.primitives.padding import PKCS7

from jwcrypto.common import InvalidCEKeyLength
from jwcrypto.common import InvalidJWAAlgorithm
from jwcrypto.common import InvalidJWEKeyLength
from jwcrypto.common import InvalidJWEKeyType
from jwcrypto.common import InvalidJWEOperation
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.common import json_decode
from jwcrypto.jwk import JWK

# Implements RFC 7518 - JSON Web Algorithms (JWA)

default_max_pbkdf2_iterations = 16384


class JWAAlgorithm(metaclass=ABCMeta):

    @property
    @abstractmethod
    def name(self):
        """The algorithm Name"""

    @property
    @abstractmethod
    def description(self):
        """A short description"""

    @property
    @abstractmethod
    def keysize(self):
        """The algorithm key size"""

    @property
    @abstractmethod
    def algorithm_usage_location(self):
        """One of 'alg', 'enc' or 'JWK'"""

    @property
    @abstractmethod
    def algorithm_use(self):
        """One of 'sig', 'kex', 'enc'"""

    @property
    def input_keysize(self):
        """The input key size"""
        try:
            return self.wrap_key_size
        except AttributeError:
            return self.keysize


def _bitsize(x):
    return len(x) * 8


def _inbytes(x):
    return x // 8


def _randombits(x):
    if x % 8 != 0:
        raise ValueError("length must be a multiple of 8")
    return os.urandom(_inbytes(x))


# Note: the number of bits should be a multiple of 16
def _encode_int(n, bits):
    e = '{:x}'.format(n)
    ilen = ((bits + 7) // 8) * 2  # number of bytes rounded up times 2 bytes
    return unhexlify(e.rjust(ilen, '0')[:ilen])


def _decode_int(n):
    return int(hexlify(n), 16)


class _RawJWS:

    def sign(self, key, payload):
        raise NotImplementedError

    def verify(self, key, payload, signature):
        raise NotImplementedError


class _RawHMAC(_RawJWS):

    def __init__(self, hashfn):
        self.backend = default_backend()
        self.hashfn = hashfn

    def _hmac_setup(self, key, payload):
        h = hmac.HMAC(key, self.hashfn, backend=self.backend)
        h.update(payload)
        return h

    def sign(self, key, payload):
        skey = base64url_decode(key.get_op_key('sign'))
        h = self._hmac_setup(skey, payload)
        return h.finalize()

    def verify(self, key, payload, signature):
        vkey = base64url_decode(key.get_op_key('verify'))
        h = self._hmac_setup(vkey, payload)
        h.verify(signature)


class _RawRSA(_RawJWS):
    def __init__(self, padfn, hashfn):
        self.padfn = padfn
        self.hashfn = hashfn

    def sign(self, key, payload):
        skey = key.get_op_key('sign')
        return skey.sign(payload, self.padfn, self.hashfn)

    def verify(self, key, payload, signature):
        pkey = key.get_op_key('verify')
        pkey.verify(signature, payload, self.padfn, self.hashfn)


class _RawEC(_RawJWS):
    def __init__(self, curve, hashfn):
        self._curve = curve
        self.hashfn = hashfn

    @property
    def curve(self):
        return self._curve

    def sign(self, key, payload):
        skey = key.get_op_key('sign', self._curve)
        size = skey.key_size
        signature = skey.sign(payload, ec.ECDSA(self.hashfn))
        r, s = ec_utils.decode_dss_signature(signature)
        return _encode_int(r, size) + _encode_int(s, size)

    def verify(self, key, payload, signature):
        pkey = key.get_op_key('verify', self._curve)
        r = signature[:len(signature) // 2]
        s = signature[len(signature) // 2:]
        enc_signature = ec_utils.encode_dss_signature(
            int(hexlify(r), 16), int(hexlify(s), 16))
        pkey.verify(enc_signature, payload, ec.ECDSA(self.hashfn))


class _RawNone(_RawJWS):

    def sign(self, key, payload):
        return ''

    def verify(self, key, payload, signature):
        if key['kty'] != 'oct' or key.get_op_key() != '':
            raise InvalidSignature('The "none" signature cannot be verified')


class _HS256(_RawHMAC, JWAAlgorithm):

    name = "HS256"
    description = "HMAC using SHA-256"
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_HS256, self).__init__(hashes.SHA256())


class _HS384(_RawHMAC, JWAAlgorithm):

    name = "HS384"
    description = "HMAC using SHA-384"
    keysize = 384
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_HS384, self).__init__(hashes.SHA384())


class _HS512(_RawHMAC, JWAAlgorithm):

    name = "HS512"
    description = "HMAC using SHA-512"
    keysize = 512
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_HS512, self).__init__(hashes.SHA512())


class _RS256(_RawRSA, JWAAlgorithm):

    name = "RS256"
    description = "RSASSA-PKCS1-v1_5 using SHA-256"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_RS256, self).__init__(padding.PKCS1v15(), hashes.SHA256())


class _RS384(_RawRSA, JWAAlgorithm):

    name = "RS384"
    description = "RSASSA-PKCS1-v1_5 using SHA-384"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_RS384, self).__init__(padding.PKCS1v15(), hashes.SHA384())


class _RS512(_RawRSA, JWAAlgorithm):

    name = "RS512"
    description = "RSASSA-PKCS1-v1_5 using SHA-512"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_RS512, self).__init__(padding.PKCS1v15(), hashes.SHA512())


class _ES256(_RawEC, JWAAlgorithm):

    name = "ES256"
    description = "ECDSA using P-256 and SHA-256"
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_ES256, self).__init__('P-256', hashes.SHA256())


class _ES256K(_RawEC, JWAAlgorithm):

    name = "ES256K"
    description = "ECDSA using secp256k1 curve and SHA-256"
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_ES256K, self).__init__('secp256k1', hashes.SHA256())


class _ES384(_RawEC, JWAAlgorithm):

    name = "ES384"
    description = "ECDSA using P-384 and SHA-384"
    keysize = 384
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_ES384, self).__init__('P-384', hashes.SHA384())


class _ES512(_RawEC, JWAAlgorithm):

    name = "ES512"
    description = "ECDSA using P-521 and SHA-512"
    keysize = 512
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_ES512, self).__init__('P-521', hashes.SHA512())


class _PS256(_RawRSA, JWAAlgorithm):

    name = "PS256"
    description = "RSASSA-PSS using SHA-256 and MGF1 with SHA-256"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        padfn = padding.PSS(padding.MGF1(hashes.SHA256()),
                            hashes.SHA256.digest_size)
        super(_PS256, self).__init__(padfn, hashes.SHA256())


class _PS384(_RawRSA, JWAAlgorithm):

    name = "PS384"
    description = "RSASSA-PSS using SHA-384 and MGF1 with SHA-384"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        padfn = padding.PSS(padding.MGF1(hashes.SHA384()),
                            hashes.SHA384.digest_size)
        super(_PS384, self).__init__(padfn, hashes.SHA384())


class _PS512(_RawRSA, JWAAlgorithm):

    name = "PS512"
    description = "RSASSA-PSS using SHA-512 and MGF1 with SHA-512"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        padfn = padding.PSS(padding.MGF1(hashes.SHA512()),
                            hashes.SHA512.digest_size)
        super(_PS512, self).__init__(padfn, hashes.SHA512())


class _None(_RawNone, JWAAlgorithm):

    name = "none"
    description = "No digital signature or MAC performed"
    keysize = 0
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'


class _RawKeyMgmt:

    def wrap(self, key, bitsize, cek, headers):
        raise NotImplementedError

    def unwrap(self, key, bitsize, ek, headers):
        raise NotImplementedError


class _RSA(_RawKeyMgmt):

    def __init__(self, padfn):
        self.padfn = padfn

    def _check_key(self, key):
        if not isinstance(key, JWK):
            raise ValueError('key is not a JWK object')
        if key['kty'] != 'RSA':
            raise InvalidJWEKeyType('RSA', key['kty'])

    # FIXME: get key size and ensure > 2048 bits
    def wrap(self, key, bitsize, cek, headers):
        self._check_key(key)
        if not cek:
            cek = _randombits(bitsize)
        rk = key.get_op_key('wrapKey')
        ek = rk.encrypt(cek, self.padfn)
        return {'cek': cek, 'ek': ek}

    def unwrap(self, key, bitsize, ek, headers):
        self._check_key(key)
        rk = key.get_op_key('unwrapKey')
        cek = rk.decrypt(ek, self.padfn)
        if _bitsize(cek) != bitsize:
            raise InvalidJWEKeyLength(bitsize, _bitsize(cek))
        return cek


class _Rsa15(_RSA, JWAAlgorithm):

    name = 'RSA1_5'
    description = "RSAES-PKCS1-v1_5"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'

    def __init__(self):
        super(_Rsa15, self).__init__(padding.PKCS1v15())

    def unwrap(self, key, bitsize, ek, headers):
        self._check_key(key)
        # Address MMA attack by implementing RFC 3218 - 2.3.2. Random Filling
        # provides a random cek that will cause the decryption engine to
        # run to the end, but will fail decryption later.

        # always generate a random cek so we spend roughly the
        # same time as in the exception side of the branch
        cek = _randombits(bitsize)
        try:
            cek = super(_Rsa15, self).unwrap(key, bitsize, ek, headers)
            # always raise so we always run through the exception handling
            # code in all cases
            raise ValueError('Dummy')
        except Exception:  # pylint: disable=broad-except
            return cek


class _RsaOaep(_RSA, JWAAlgorithm):

    name = 'RSA-OAEP'
    description = "RSAES OAEP using default parameters"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'

    def __init__(self):
        super(_RsaOaep, self).__init__(
            padding.OAEP(padding.MGF1(hashes.SHA1()),
                         hashes.SHA1(), None))


class _RsaOaep256(_RSA, JWAAlgorithm):  # noqa: ignore=N801

    name = 'RSA-OAEP-256'
    description = "RSAES OAEP using SHA-256 and MGF1 with SHA-256"
    keysize = 2048
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'

    def __init__(self):
        super(_RsaOaep256, self).__init__(
            padding.OAEP(padding.MGF1(hashes.SHA256()),
                         hashes.SHA256(), None))


class _AesKw(_RawKeyMgmt):

    keysize = None

    def __init__(self):
        self.backend = default_backend()

    def _get_key(self, key, op):
        if not isinstance(key, JWK):
            raise ValueError('key is not a JWK object')
        if key['kty'] != 'oct':
            raise InvalidJWEKeyType('oct', key['kty'])
        rk = base64url_decode(key.get_op_key(op))
        if _bitsize(rk) != self.keysize:
            raise InvalidJWEKeyLength(self.keysize, _bitsize(rk))
        return rk

    def wrap(self, key, bitsize, cek, headers):
        rk = self._get_key(key, 'encrypt')
        if not cek:
            cek = _randombits(bitsize)

        ek = aes_key_wrap(rk, cek, default_backend())

        return {'cek': cek, 'ek': ek}

    def unwrap(self, key, bitsize, ek, headers):
        rk = self._get_key(key, 'decrypt')

        cek = aes_key_unwrap(rk, ek, default_backend())
        if _bitsize(cek) != bitsize:
            raise InvalidJWEKeyLength(bitsize, _bitsize(cek))
        return cek


class _A128KW(_AesKw, JWAAlgorithm):

    name = 'A128KW'
    description = "AES Key Wrap using 128-bit key"
    keysize = 128
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _A192KW(_AesKw, JWAAlgorithm):

    name = 'A192KW'
    description = "AES Key Wrap using 192-bit key"
    keysize = 192
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _A256KW(_AesKw, JWAAlgorithm):

    name = 'A256KW'
    description = "AES Key Wrap using 256-bit key"
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _AesGcmKw(_RawKeyMgmt):

    keysize = None

    def __init__(self):
        self.backend = default_backend()

    def _get_key(self, key, op):
        if not isinstance(key, JWK):
            raise ValueError('key is not a JWK object')
        if key['kty'] != 'oct':
            raise InvalidJWEKeyType('oct', key['kty'])
        rk = base64url_decode(key.get_op_key(op))
        if _bitsize(rk) != self.keysize:
            raise InvalidJWEKeyLength(self.keysize, _bitsize(rk))
        return rk

    def wrap(self, key, bitsize, cek, headers):
        rk = self._get_key(key, 'encrypt')
        if not cek:
            cek = _randombits(bitsize)

        iv = _randombits(96)
        cipher = Cipher(algorithms.AES(rk), modes.GCM(iv),
                        backend=self.backend)
        encryptor = cipher.encryptor()
        ek = encryptor.update(cek) + encryptor.finalize()

        tag = encryptor.tag
        return {'cek': cek, 'ek': ek,
                'header': {'iv': base64url_encode(iv),
                           'tag': base64url_encode(tag)}}

    def unwrap(self, key, bitsize, ek, headers):
        rk = self._get_key(key, 'decrypt')

        if 'iv' not in headers:
            raise ValueError('Invalid Header, missing "iv" parameter')
        iv = base64url_decode(headers['iv'])
        if 'tag' not in headers:
            raise ValueError('Invalid Header, missing "tag" parameter')
        tag = base64url_decode(headers['tag'])

        cipher = Cipher(algorithms.AES(rk), modes.GCM(iv, tag),
                        backend=self.backend)
        decryptor = cipher.decryptor()
        cek = decryptor.update(ek) + decryptor.finalize()
        if _bitsize(cek) != bitsize:
            raise InvalidJWEKeyLength(bitsize, _bitsize(cek))
        return cek


class _A128GcmKw(_AesGcmKw, JWAAlgorithm):

    name = 'A128GCMKW'
    description = "Key wrapping with AES GCM using 128-bit key"
    keysize = 128
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _A192GcmKw(_AesGcmKw, JWAAlgorithm):

    name = 'A192GCMKW'
    description = "Key wrapping with AES GCM using 192-bit key"
    keysize = 192
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _A256GcmKw(_AesGcmKw, JWAAlgorithm):

    name = 'A256GCMKW'
    description = "Key wrapping with AES GCM using 256-bit key"
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _Pbes2HsAesKw(_RawKeyMgmt):

    name = None
    keysize = None
    hashsize = None

    def __init__(self):
        self.backend = default_backend()
        self.aeskwmap = {128: _A128KW, 192: _A192KW, 256: _A256KW}

    def _get_key(self, alg, key, p2s, p2c):
        if p2c > default_max_pbkdf2_iterations:
            raise ValueError('Invalid p2c value, too large')

        if not isinstance(key, JWK):
            # backwards compatibility for old interface
            if isinstance(key, bytes):
                plain = key
            else:
                plain = key.encode('utf8')
        else:
            plain = base64url_decode(key.get_op_key())

        salt = bytes(self.name.encode('utf8')) + b'\x00' + p2s

        if self.hashsize == 256:
            hashalg = hashes.SHA256()
        elif self.hashsize == 384:
            hashalg = hashes.SHA384()
        elif self.hashsize == 512:
            hashalg = hashes.SHA512()
        else:
            raise ValueError('Unknown Hash Size')

        kdf = PBKDF2HMAC(algorithm=hashalg, length=_inbytes(self.keysize),
                         salt=salt, iterations=p2c, backend=self.backend)
        rk = kdf.derive(plain)
        if _bitsize(rk) != self.keysize:
            raise InvalidJWEKeyLength(self.keysize, len(rk))
        return JWK(kty="oct", use="enc", k=base64url_encode(rk))

    def wrap(self, key, bitsize, cek, headers):
        ret_header = {}
        if 'p2s' in headers:
            p2s = base64url_decode(headers['p2s'])
            if len(p2s) < 8:
                raise ValueError('Invalid Salt, must be 8 or more octects')
        else:
            p2s = _randombits(128)
            ret_header['p2s'] = base64url_encode(p2s)
        if 'p2c' in headers:
            p2c = headers['p2c']
        else:
            p2c = 8192
            ret_header['p2c'] = p2c
        kek = self._get_key(headers['alg'], key, p2s, p2c)

        aeskw = self.aeskwmap[self.keysize]()
        ret = aeskw.wrap(kek, bitsize, cek, headers)
        if len(ret_header) > 0:
            ret['header'] = ret_header
        return ret

    def unwrap(self, key, bitsize, ek, headers):
        if 'p2s' not in headers:
            raise ValueError('Invalid Header, missing "p2s" parameter')
        if 'p2c' not in headers:
            raise ValueError('Invalid Header, missing "p2c" parameter')
        p2s = base64url_decode(headers['p2s'])
        p2c = headers['p2c']
        kek = self._get_key(headers['alg'], key, p2s, p2c)

        aeskw = self.aeskwmap[self.keysize]()
        return aeskw.unwrap(kek, bitsize, ek, headers)


class _Pbes2Hs256A128Kw(_Pbes2HsAesKw, JWAAlgorithm):

    name = 'PBES2-HS256+A128KW'
    description = 'PBES2 with HMAC SHA-256 and "A128KW" wrapping'
    keysize = 128
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'
    hashsize = 256


class _Pbes2Hs384A192Kw(_Pbes2HsAesKw, JWAAlgorithm):

    name = 'PBES2-HS384+A192KW'
    description = 'PBES2 with HMAC SHA-384 and "A192KW" wrapping'
    keysize = 192
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'
    hashsize = 384


class _Pbes2Hs512A256Kw(_Pbes2HsAesKw, JWAAlgorithm):

    name = 'PBES2-HS512+A256KW'
    description = 'PBES2 with HMAC SHA-512 and "A256KW" wrapping'
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'
    hashsize = 512


class _Direct(_RawKeyMgmt, JWAAlgorithm):

    name = 'dir'
    description = "Direct use of a shared symmetric key"
    keysize = 128
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'

    def _check_key(self, key):
        if not isinstance(key, JWK):
            raise ValueError('key is not a JWK object')
        if key['kty'] != 'oct':
            raise InvalidJWEKeyType('oct', key['kty'])

    def wrap(self, key, bitsize, cek, headers):
        self._check_key(key)
        if cek:
            return (cek, None)
        k = base64url_decode(key.get_op_key('encrypt'))
        if _bitsize(k) != bitsize:
            raise InvalidCEKeyLength(bitsize, _bitsize(k))
        return {'cek': k}

    def unwrap(self, key, bitsize, ek, headers):
        self._check_key(key)
        if ek != b'':
            raise ValueError('Invalid Encryption Key.')
        cek = base64url_decode(key.get_op_key('decrypt'))
        if _bitsize(cek) != bitsize:
            raise InvalidJWEKeyLength(bitsize, _bitsize(cek))
        return cek


class _EcdhEs(_RawKeyMgmt, JWAAlgorithm):

    name = 'ECDH-ES'
    description = "ECDH-ES using Concat KDF"
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'
    keysize = None

    def __init__(self):
        self.backend = default_backend()
        self.aeskwmap = {128: _A128KW, 192: _A192KW, 256: _A256KW}

    def _check_key(self, key):
        if not isinstance(key, JWK):
            raise ValueError('key is not a JWK object')
        if key['kty'] not in ['EC', 'OKP']:
            raise InvalidJWEKeyType('EC or OKP', key['kty'])
        if key['kty'] == 'OKP':
            if key['crv'] not in ['X25519', 'X448']:
                raise InvalidJWEKeyType('X25519 or X448',
                                        key['crv'])

    def _derive(self, privkey, pubkey, alg, bitsize, headers):
        # OtherInfo is defined in NIST SP 56A 5.8.1.2.1

        # AlgorithmID
        otherinfo = struct.pack('>I', len(alg))
        otherinfo += bytes(alg.encode('utf8'))

        # PartyUInfo
        apu = base64url_decode(headers['apu']) if 'apu' in headers else b''
        otherinfo += struct.pack('>I', len(apu))
        otherinfo += apu

        # PartyVInfo
        apv = base64url_decode(headers['apv']) if 'apv' in headers else b''
        otherinfo += struct.pack('>I', len(apv))
        otherinfo += apv

        # SuppPubInfo
        otherinfo += struct.pack('>I', bitsize)

        # no SuppPrivInfo

        # Shared Key generation
        if isinstance(privkey, ec.EllipticCurvePrivateKey):
            shared_key = privkey.exchange(ec.ECDH(), pubkey)
        else:
            # X25519/X448
            shared_key = privkey.exchange(pubkey)

        ckdf = ConcatKDFHash(algorithm=hashes.SHA256(),
                             length=_inbytes(bitsize),
                             otherinfo=otherinfo,
                             backend=self.backend)
        return ckdf.derive(shared_key)

    def wrap(self, key, bitsize, cek, headers):
        self._check_key(key)
        dk_size = self.keysize
        if self.keysize is None:
            if cek is not None:
                raise InvalidJWEOperation('ECDH-ES cannot use an existing CEK')
            alg = headers['enc']
            dk_size = bitsize
        else:
            alg = headers['alg']

        epk = JWK.generate(kty=key['kty'], crv=key['crv'])
        dk = self._derive(epk.get_op_key('unwrapKey'),
                          key.get_op_key('wrapKey'),
                          alg, dk_size, headers)

        if self.keysize is None:
            ret = {'cek': dk}
        else:
            aeskw = self.aeskwmap[self.keysize]()
            kek = JWK(kty="oct", use="enc", k=base64url_encode(dk))
            ret = aeskw.wrap(kek, bitsize, cek, headers)

        ret['header'] = {'epk': json_decode(epk.export_public())}
        return ret

    def unwrap(self, key, bitsize, ek, headers):
        if 'epk' not in headers:
            raise ValueError('Invalid Header, missing "epk" parameter')
        self._check_key(key)
        dk_size = self.keysize
        if self.keysize is None:
            alg = headers['enc']
            dk_size = bitsize
        else:
            alg = headers['alg']

        epk = JWK(**headers['epk'])
        dk = self._derive(key.get_op_key('unwrapKey'),
                          epk.get_op_key('wrapKey'),
                          alg, dk_size, headers)
        if self.keysize is None:
            return dk
        else:
            aeskw = self.aeskwmap[self.keysize]()
            kek = JWK(kty="oct", use="enc", k=base64url_encode(dk))
            cek = aeskw.unwrap(kek, bitsize, ek, headers)
            return cek


class _EcdhEsAes128Kw(_EcdhEs):

    name = 'ECDH-ES+A128KW'
    description = 'ECDH-ES using Concat KDF and "A128KW" wrapping'
    keysize = 128
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _EcdhEsAes192Kw(_EcdhEs):

    name = 'ECDH-ES+A192KW'
    description = 'ECDH-ES using Concat KDF and "A192KW" wrapping'
    keysize = 192
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _EcdhEsAes256Kw(_EcdhEs):

    name = 'ECDH-ES+A256KW'
    description = 'ECDH-ES using Concat KDF and "A256KW" wrapping'
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'kex'


class _EdDsa(_RawJWS, JWAAlgorithm):

    name = 'EdDSA'
    description = 'EdDSA using Ed25519 or Ed448 algorithms'
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'
    keysize = None

    def sign(self, key, payload):
        if key['crv'] in ['Ed25519', 'Ed448']:
            skey = key.get_op_key('sign')
            return skey.sign(payload)
        raise NotImplementedError

    def verify(self, key, payload, signature):
        if key['crv'] in ['Ed25519', 'Ed448']:
            pkey = key.get_op_key('verify')
            return pkey.verify(signature, payload)
        raise NotImplementedError


class _RawJWE:

    def encrypt(self, k, aad, m):
        raise NotImplementedError

    def decrypt(self, k, aad, iv, e, t):
        raise NotImplementedError


class _AesCbcHmacSha2(_RawJWE):

    keysize = None

    def __init__(self, hashfn):
        self.backend = default_backend()
        self.hashfn = hashfn
        self.blocksize = algorithms.AES.block_size
        self.wrap_key_size = self.keysize * 2

    def _mac(self, k, aad, iv, e):
        al = _encode_int(_bitsize(aad), 64)
        h = hmac.HMAC(k, self.hashfn, backend=self.backend)
        h.update(aad)
        h.update(iv)
        h.update(e)
        h.update(al)
        m = h.finalize()
        return m[:_inbytes(self.keysize)]

    # RFC 7518 - 5.2.2
    def encrypt(self, k, aad, m):
        """ Encrypt according to the selected encryption and hashing
        functions.

        :param k: Encryption key
        :param aad: Additional Authentication Data
        :param m: Plaintext

        Returns a dictionary with the computed data.
        """
        if len(k) != _inbytes(self.wrap_key_size):
            raise ValueError("Invalid input key size")

        hkey = k[:_inbytes(self.keysize)]
        ekey = k[_inbytes(self.keysize):]

        # encrypt
        iv = _randombits(self.blocksize)
        cipher = Cipher(algorithms.AES(ekey), modes.CBC(iv),
                        backend=self.backend)
        encryptor = cipher.encryptor()
        padder = PKCS7(self.blocksize).padder()
        padded_data = padder.update(m) + padder.finalize()
        e = encryptor.update(padded_data) + encryptor.finalize()

        # mac
        t = self._mac(hkey, aad, iv, e)

        return (iv, e, t)

    def decrypt(self, k, aad, iv, e, t):
        """ Decrypt according to the selected encryption and hashing
        functions.
        :param k: Encryption key
        :param aad: Additional Authenticated Data
        :param iv: Initialization Vector
        :param e: Ciphertext
        :param t: Authentication Tag

        Returns plaintext or raises an error
        """
        if len(k) != _inbytes(self.wrap_key_size):
            raise ValueError("Invalid input key size")

        hkey = k[:_inbytes(self.keysize)]
        dkey = k[_inbytes(self.keysize):]

        # verify mac
        if not constant_time.bytes_eq(t, self._mac(hkey, aad, iv, e)):
            raise InvalidSignature('Failed to verify MAC')

        # decrypt
        cipher = Cipher(algorithms.AES(dkey), modes.CBC(iv),
                        backend=self.backend)
        decryptor = cipher.decryptor()
        d = decryptor.update(e) + decryptor.finalize()
        unpadder = PKCS7(self.blocksize).unpadder()
        return unpadder.update(d) + unpadder.finalize()


class _A128CbcHs256(_AesCbcHmacSha2, JWAAlgorithm):

    name = 'A128CBC-HS256'
    description = "AES_128_CBC_HMAC_SHA_256 authenticated"
    keysize = 128
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'

    def __init__(self):
        super(_A128CbcHs256, self).__init__(hashes.SHA256())


class _A192CbcHs384(_AesCbcHmacSha2, JWAAlgorithm):

    name = 'A192CBC-HS384'
    description = "AES_192_CBC_HMAC_SHA_384 authenticated"
    keysize = 192
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'

    def __init__(self):
        super(_A192CbcHs384, self).__init__(hashes.SHA384())


class _A256CbcHs512(_AesCbcHmacSha2, JWAAlgorithm):

    name = 'A256CBC-HS512'
    description = "AES_256_CBC_HMAC_SHA_512 authenticated"
    keysize = 256
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'

    def __init__(self):
        super(_A256CbcHs512, self).__init__(hashes.SHA512())


class _AesGcm(_RawJWE):

    keysize = None

    def __init__(self):
        self.backend = default_backend()
        self.wrap_key_size = self.keysize

    # RFC 7518 - 5.3
    def encrypt(self, k, aad, m):
        """ Encrypt according to the selected encryption and hashing
        functions.

        :param k: Encryption key
        :param aad: Additional Authentication Data
        :param m: Plaintext

        Returns a dictionary with the computed data.
        """
        iv = _randombits(96)
        cipher = Cipher(algorithms.AES(k), modes.GCM(iv),
                        backend=self.backend)
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(aad)
        e = encryptor.update(m) + encryptor.finalize()

        return (iv, e, encryptor.tag)

    def decrypt(self, k, aad, iv, e, t):
        """ Decrypt according to the selected encryption and hashing
        functions.
        :param k: Encryption key
        :param aad: Additional Authenticated Data
        :param iv: Initialization Vector
        :param e: Ciphertext
        :param t: Authentication Tag

        Returns plaintext or raises an error
        """
        cipher = Cipher(algorithms.AES(k), modes.GCM(iv, t),
                        backend=self.backend)
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(aad)
        return decryptor.update(e) + decryptor.finalize()


class _A128Gcm(_AesGcm, JWAAlgorithm):

    name = 'A128GCM'
    description = "AES GCM using 128-bit key"
    keysize = 128
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'


class _A192Gcm(_AesGcm, JWAAlgorithm):

    name = 'A192GCM'
    description = "AES GCM using 192-bit key"
    keysize = 192
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'


class _A256Gcm(_AesGcm, JWAAlgorithm):

    name = 'A256GCM'
    description = "AES GCM using 256-bit key"
    keysize = 256
    algorithm_usage_location = 'enc'
    algorithm_use = 'enc'


class _BP256R1(_RawEC, JWAAlgorithm):

    name = "BP256R1"
    description = (
        "ECDSA using Brainpool256R1 curve and SHA-256"
        " (unregistered, custom-defined in breach"
        " of IETF rules by gematik GmbH)"
    )
    keysize = 256
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_BP256R1, self).__init__('BP-256', hashes.SHA256())


class _BP384R1(_RawEC, JWAAlgorithm):

    name = "BP384R1"
    description = (
        "ECDSA using Brainpool384R1 curve and SHA-384"
        " (unregistered, custom-defined in breach"
        " of IETF rules by gematik GmbH)"
    )
    keysize = 384
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_BP384R1, self).__init__('BP-384', hashes.SHA384())


class _BP512R1(_RawEC, JWAAlgorithm):

    name = "BP512R1"
    description = (
        "ECDSA using Brainpool512R1 curve and SHA-512"
        " (unregistered, custom-defined in breach"
        " of IETF rules by gematik GmbH)"
    )
    keysize = 512
    algorithm_usage_location = 'alg'
    algorithm_use = 'sig'

    def __init__(self):
        super(_BP512R1, self).__init__('BP-512', hashes.SHA512())


class JWA:
    """JWA Signing Algorithms.

    This class provides access to all JWA algorithms.
    """

    algorithms_registry = {
        'HS256': _HS256,
        'HS384': _HS384,
        'HS512': _HS512,
        'RS256': _RS256,
        'RS384': _RS384,
        'RS512': _RS512,
        'ES256': _ES256,
        'ES256K': _ES256K,
        'ES384': _ES384,
        'ES512': _ES512,
        'PS256': _PS256,
        'PS384': _PS384,
        'PS512': _PS512,
        'none': _None,
        'RSA1_5': _Rsa15,
        'RSA-OAEP': _RsaOaep,
        'RSA-OAEP-256': _RsaOaep256,
        'A128KW': _A128KW,
        'A192KW': _A192KW,
        'A256KW': _A256KW,
        'dir': _Direct,
        'ECDH-ES': _EcdhEs,
        'ECDH-ES+A128KW': _EcdhEsAes128Kw,
        'ECDH-ES+A192KW': _EcdhEsAes192Kw,
        'ECDH-ES+A256KW': _EcdhEsAes256Kw,
        'EdDSA': _EdDsa,
        'A128GCMKW': _A128GcmKw,
        'A192GCMKW': _A192GcmKw,
        'A256GCMKW': _A256GcmKw,
        'PBES2-HS256+A128KW': _Pbes2Hs256A128Kw,
        'PBES2-HS384+A192KW': _Pbes2Hs384A192Kw,
        'PBES2-HS512+A256KW': _Pbes2Hs512A256Kw,
        'A128CBC-HS256': _A128CbcHs256,
        'A192CBC-HS384': _A192CbcHs384,
        'A256CBC-HS512': _A256CbcHs512,
        'A128GCM': _A128Gcm,
        'A192GCM': _A192Gcm,
        'A256GCM': _A256Gcm,
        'BP256R1': _BP256R1,
        'BP384R1': _BP384R1,
        'BP512R1': _BP512R1
    }

    @classmethod
    def instantiate_alg(cls, name, use=None):
        alg = cls.algorithms_registry[name]
        if use is not None and alg.algorithm_use != use:
            raise KeyError
        return alg()

    @classmethod
    def signing_alg(cls, name):
        try:
            return cls.instantiate_alg(name, use='sig')
        except KeyError:
            raise InvalidJWAAlgorithm('%s is not a valid Signing algorithm'
                                      ' name' % name) from None

    @classmethod
    def keymgmt_alg(cls, name):
        try:
            return cls.instantiate_alg(name, use='kex')
        except KeyError:
            raise InvalidJWAAlgorithm('%s is not a valid Key Management'
                                      ' algorithm name' % name) from None

    @classmethod
    def encryption_alg(cls, name):
        try:
            return cls.instantiate_alg(name, use='enc')
        except KeyError:
            raise InvalidJWAAlgorithm('%s is not a valid Encryption'
                                      ' algorithm name' % name) from None
