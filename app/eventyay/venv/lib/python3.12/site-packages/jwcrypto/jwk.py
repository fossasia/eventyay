# Copyright (C) 2015  JWCrypto Project Contributors - see LICENSE file

import os
from binascii import hexlify, unhexlify
from collections import namedtuple
from enum import Enum

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric import rsa

from typing_extensions import deprecated

from jwcrypto.common import JWException
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.common import json_decode, json_encode


class UnimplementedOKPCurveKey:
    @classmethod
    def generate(cls):
        raise NotImplementedError

    @classmethod
    def from_public_bytes(cls, *args):
        raise NotImplementedError

    @classmethod
    def from_private_bytes(cls, *args):
        raise NotImplementedError


ImplementedOkpCurves = []


# Handle the best we can older versions of python cryptography that
# do not yet implement these interfaces properly
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey, Ed25519PrivateKey
    )
    ImplementedOkpCurves.append('Ed25519')
except ImportError:
    Ed25519PublicKey = UnimplementedOKPCurveKey
    Ed25519PrivateKey = UnimplementedOKPCurveKey
try:
    from cryptography.hazmat.primitives.asymmetric.ed448 import (
        Ed448PublicKey, Ed448PrivateKey
    )
    ImplementedOkpCurves.append('Ed448')
except ImportError:
    Ed448PublicKey = UnimplementedOKPCurveKey
    Ed448PrivateKey = UnimplementedOKPCurveKey
try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PublicKey, X25519PrivateKey
    )
    priv_bytes = getattr(X25519PrivateKey, 'from_private_bytes', None)
    if priv_bytes is None:
        raise ImportError
    ImplementedOkpCurves.append('X25519')
except ImportError:
    X25519PublicKey = UnimplementedOKPCurveKey
    X25519PrivateKey = UnimplementedOKPCurveKey
try:
    from cryptography.hazmat.primitives.asymmetric.x448 import (
        X448PublicKey, X448PrivateKey
    )
    ImplementedOkpCurves.append('X448')
except ImportError:
    X448PublicKey = UnimplementedOKPCurveKey
    X448PrivateKey = UnimplementedOKPCurveKey


_Ed25519_CURVE = namedtuple('Ed25519', 'pubkey privkey')
_Ed448_CURVE = namedtuple('Ed448', 'pubkey privkey')
_X25519_CURVE = namedtuple('X25519', 'pubkey privkey')
_X448_CURVE = namedtuple('X448', 'pubkey privkey')
_OKP_CURVES_TABLE = {
    'Ed25519': _Ed25519_CURVE(Ed25519PublicKey, Ed25519PrivateKey),
    'Ed448': _Ed448_CURVE(Ed448PublicKey, Ed448PrivateKey),
    'X25519': _X25519_CURVE(X25519PublicKey, X25519PrivateKey),
    'X448': _X448_CURVE(X448PublicKey, X448PrivateKey)
}


# RFC 7518 - 7.4 , RFC 8037 - 5
JWKTypesRegistry = {'EC': 'Elliptic Curve',
                    'RSA': 'RSA',
                    'oct': 'Octet sequence',
                    'OKP': 'Octet Key Pair'}
"""Registry of valid Key Types"""


# RFC 7518 - 7.5
# It is part of the JWK Parameters Registry, but we want a more
# specific map for internal usage
class ParmType(Enum):
    name = 'A string with a name'
    b64 = 'Base64url Encoded'
    b64u = 'Base64urlUint Encoded'
    unsupported = 'Unsupported Parameter'


JWKParameter = namedtuple('Parameter', 'description public required type')
JWKValuesRegistry = {
    'EC': {
        'crv': JWKParameter('Curve', True, True, ParmType.name),
        'x': JWKParameter('X Coordinate', True, True, ParmType.b64),
        'y': JWKParameter('Y Coordinate', True, True, ParmType.b64),
        'd': JWKParameter('ECC Private Key', False, False, ParmType.b64),
    },
    'RSA': {
        'n': JWKParameter('Modulus', True, True, ParmType.b64),
        'e': JWKParameter('Exponent', True, True, ParmType.b64u),
        'd': JWKParameter('Private Exponent', False, False, ParmType.b64u),
        'p': JWKParameter('First Prime Factor', False, False, ParmType.b64u),
        'q': JWKParameter('Second Prime Factor', False, False, ParmType.b64u),
        'dp': JWKParameter('First Factor CRT Exponent',
                           False, False, ParmType.b64u),
        'dq': JWKParameter('Second Factor CRT Exponent',
                           False, False, ParmType.b64u),
        'qi': JWKParameter('First CRT Coefficient',
                           False, False, ParmType.b64u),
        'oth': JWKParameter('Other Primes Info',
                            False, False, ParmType.unsupported),
    },
    'oct': {
        'k': JWKParameter('Key Value', False, True, ParmType.b64),
    },
    'OKP': {
        'crv': JWKParameter('Curve', True, True, ParmType.name),
        'x': JWKParameter('Public Key', True, True, ParmType.b64),
        'd': JWKParameter('Private Key', False, False, ParmType.b64),
    }
}
"""Registry of valid key values"""

JWKParamsRegistry = {
    'kty': JWKParameter('Key Type', True, None, None),
    'use': JWKParameter('Public Key Use', True, None, None),
    'key_ops': JWKParameter('Key Operations', True, None, None),
    'alg': JWKParameter('Algorithm', True, None, None),
    'kid': JWKParameter('Key ID', True, None, None),
    'x5u': JWKParameter('X.509 URL', True, None, None),
    'x5c': JWKParameter('X.509 Certificate Chain', True, None, None),
    'x5t': JWKParameter('X.509 Certificate SHA-1 Thumbprint',
                        True, None, None),
    'x5t#S256': JWKParameter('X.509 Certificate SHA-256 Thumbprint',
                             True, None, None)
}
"""Registry of valid key parameters"""

# RFC 7518 - 7.6 , RFC 8037 - 5
# RFC 8812 - 4.4
JWKEllipticCurveRegistry = {'P-256': 'P-256 curve',
                            'P-384': 'P-384 curve',
                            'P-521': 'P-521 curve',
                            'secp256k1': 'SECG secp256k1 curve',
                            'Ed25519': 'Ed25519 signature algorithm key pairs',
                            'Ed448': 'Ed448 signature algorithm key pairs',
                            'X25519': 'X25519 function key pairs',
                            'X448': 'X448 function key pairs',
                            'BP-256': 'BrainpoolP256R1 curve'
                                    ' (unregistered, custom-defined in breach'
                                    ' of IETF rules by gematik GmbH)',
                            'BP-384': 'BrainpoolP384R1 curve'
                                    ' (unregistered, custom-defined in breach'
                                    ' of IETF rules by gematik GmbH)',
                            'BP-512': 'BrainpoolP512R1 curve'
                                    ' (unregistered, custom-defined in breach'
                                    ' of IETF rules by gematik GmbH)'
                            }
"""Registry of allowed Elliptic Curves"""

# RFC 7517 - 8.2
JWKUseRegistry = {'sig': 'Digital Signature or MAC',
                  'enc': 'Encryption'}
"""Registry of allowed uses"""

# RFC 7517 - 8.3
JWKOperationsRegistry = {'sign': 'Compute digital Signature or MAC',
                         'verify': 'Verify digital signature or MAC',
                         'encrypt': 'Encrypt content',
                         'decrypt': 'Decrypt content and validate'
                                    ' decryption, if applicable',
                         'wrapKey': 'Encrypt key',
                         'unwrapKey': 'Decrypt key and validate'
                                    ' decryption, if applicable',
                         'deriveKey': 'Derive key',
                         'deriveBits': 'Derive bits not to be used as a key'}
"""Registry of allowed operations"""

JWKpycaCurveMap = {'secp256r1': 'P-256',
                   'secp384r1': 'P-384',
                   'secp521r1': 'P-521',
                   'secp256k1': 'secp256k1',
                   'brainpoolP256r1': 'BP-256',
                   'brainpoolP384r1': 'BP-384',
                   'brainpoolP512r1': 'BP-512'}

IANANamedInformationHashAlgorithmRegistry = {
    'sha-256': hashes.SHA256(),
    'sha-256-128': None,
    'sha-256-120': None,
    'sha-256-96': None,
    'sha-256-64': None,
    'sha-256-32': None,
    'sha-384': hashes.SHA384(),
    'sha-512': hashes.SHA512(),
    'sha3-224': hashes.SHA3_224(),
    'sha3-256': hashes.SHA3_256(),
    'sha3-384': hashes.SHA3_384(),
    'sha3-512': hashes.SHA3_512(),
    'blake2s-256': hashes.BLAKE2s(32),
    'blake2b-256': None,  # pyca supports only 64 bytes for BLAKEb
    'blake2b-512': hashes.BLAKE2b(64),
}


class InvalidJWKType(JWException):
    """Invalid JWK Type Exception.

    This exception is raised when an invalid parameter type is used.
    """

    def __init__(self, value=None):
        super(InvalidJWKType, self).__init__()
        self.value = value

    def __str__(self):
        return 'Unknown type "%s", valid types are: %s' % (
            self.value, list(JWKTypesRegistry.keys()))


class InvalidJWKUsage(JWException):
    """Invalid JWK usage Exception.

    This exception is raised when an invalid key usage is requested,
    based on the key type and declared usage constraints.
    """

    def __init__(self, use, value):
        super(InvalidJWKUsage, self).__init__()
        self.value = value
        self.use = use

    def __str__(self):
        if self.use in list(JWKUseRegistry.keys()):
            usage = JWKUseRegistry[self.use]
        else:
            usage = 'Unknown(%s)' % self.use
        if self.value in list(JWKUseRegistry.keys()):
            valid = JWKUseRegistry[self.value]
        else:
            valid = 'Unknown(%s)' % self.value
        return 'Invalid usage requested: "%s". Valid for: "%s"' % (usage,
                                                                   valid)


class InvalidJWKOperation(JWException):
    """Invalid JWK Operation Exception.

    This exception is raised when an invalid key operation is requested,
    based on the key type and declared usage constraints.
    """

    def __init__(self, operation, values):
        super(InvalidJWKOperation, self).__init__()
        self.op = operation
        self.values = values

    def __str__(self):
        if self.op in list(JWKOperationsRegistry.keys()):
            op = JWKOperationsRegistry[self.op]
        else:
            op = 'Unknown(%s)' % self.op
        valid = []
        for v in self.values:
            if v in list(JWKOperationsRegistry.keys()):
                valid.append(JWKOperationsRegistry[v])
            else:
                valid.append('Unknown(%s)' % v)
        return 'Invalid operation requested: "%s". Valid for: "%s"' % (op,
                                                                       valid)


class InvalidJWKValue(JWException):
    """Invalid JWK Value Exception.

    This exception is raised when an invalid/unknown value is used in the
    context of an operation that requires specific values to be used based
    on the key type or other constraints.
    """


class JWK(dict):
    """JSON Web Key object

    This object represents a Key.
    It must be instantiated by using the standard defined key/value pairs
    as arguments of the initialization function.
    """

    def __init__(self, **kwargs):
        r"""Creates a new JWK object.

        The function arguments must be valid parameters as defined in the
        'IANA JSON Web Key Set Parameters registry' and specified in
        the :data:`JWKParamsRegistry` variable. The 'kty' parameter must
        always be provided and its value must be a valid one as defined
        by the 'IANA JSON Web Key Types registry' and specified in the
        :data:`JWKTypesRegistry` variable. The valid key parameters per
        key type are defined in the :data:`JWKValuesRegistry` variable.

        To generate a new random key call the class method generate() with
        the appropriate 'kty' parameter, and other parameters as needed (key
        size, public exponents, curve types, etc..)

        Valid options per type, when generating new keys:
         * oct: size(int)
         * RSA: public_exponent(int), size(int)
         * EC: crv(str) (one of P-256, P-384, P-521, secp256k1)
         * OKP: crv(str) (one of Ed25519, Ed448, X25519, X448)

        Deprecated:
        Alternatively if the 'generate' parameter is provided with a
        valid key type as value then a new key will be generated according
        to the defaults or provided key strength options (type specific).

        :param \**kwargs: parameters (optional).

        :raises InvalidJWKType: if the key type is invalid
        :raises InvalidJWKValue: if incorrect or inconsistent parameters
            are provided.
        """
        super(JWK, self).__init__()
        self._cache_pub_k = None
        self._cache_pri_k = None

        if 'generate' in kwargs:
            self.generate_key(**kwargs)
        elif kwargs:
            self.import_key(**kwargs)

    @classmethod
    def generate(cls, **kwargs):
        obj = cls()
        kty = None
        try:
            kty = kwargs['kty']
            gen = getattr(obj, '_generate_%s' % kty)
        except (KeyError, AttributeError) as e:
            raise InvalidJWKType(kty) from e
        gen(kwargs)
        return obj

    def generate_key(self, **params):
        kty = None
        try:
            kty = params.pop('generate')
            gen = getattr(self, '_generate_%s' % kty)
        except (KeyError, AttributeError) as e:
            raise InvalidJWKType(kty) from e

        gen(params)

    def _get_gen_size(self, params, default_size=None):
        size = default_size
        if 'size' in params:
            size = params.pop('size')
        elif 'alg' in params:
            try:
                from jwcrypto.jwa import JWA
                alg = JWA.instantiate_alg(params['alg'])
            except KeyError as e:
                raise ValueError("Invalid 'alg' parameter") from e
            size = alg.input_keysize
        return size

    def _generate_oct(self, params):
        size = self._get_gen_size(params, 128)
        key = os.urandom(size // 8)
        params['kty'] = 'oct'
        params['k'] = base64url_encode(key)
        self.import_key(**params)

    def _encode_int(self, i, bit_size=None):
        extend = 0
        if bit_size is not None:
            extend = ((bit_size + 7) // 8) * 2
        hexi = hex(i).rstrip("L").lstrip("0x")
        hexl = len(hexi)
        if extend > hexl:
            extend -= hexl
        else:
            extend = hexl % 2
        return base64url_encode(unhexlify(extend * '0' + hexi))

    def _generate_RSA(self, params):
        pubexp = 65537
        size = self._get_gen_size(params, 2048)
        if 'public_exponent' in params:
            pubexp = params.pop('public_exponent')
        key = rsa.generate_private_key(pubexp, size, default_backend())
        self._import_pyca_pri_rsa(key, **params)

    def _import_pyca_pri_rsa(self, key, **params):
        pn = key.private_numbers()
        params.update(
            kty='RSA',
            n=self._encode_int(pn.public_numbers.n),
            e=self._encode_int(pn.public_numbers.e),
            d=self._encode_int(pn.d),
            p=self._encode_int(pn.p),
            q=self._encode_int(pn.q),
            dp=self._encode_int(pn.dmp1),
            dq=self._encode_int(pn.dmq1),
            qi=self._encode_int(pn.iqmp)
        )
        self.import_key(**params)

    def _import_pyca_pub_rsa(self, key, **params):
        pn = key.public_numbers()
        params.update(
            kty='RSA',
            n=self._encode_int(pn.n),
            e=self._encode_int(pn.e)
        )
        self.import_key(**params)

    def _get_curve_by_name(self, name, ctype=None):
        crv = self.get('crv')

        if name is None:
            cname = crv
        elif name == 'P-256K':
            # P-256K is an alias for 'secp256k1' to handle compatibility
            # with some implementation using this old drafting name
            cname = 'secp256k1'
        else:
            cname = name

        # Check we are asking for the correct curve unless this is being
        # requested for generation on a blank JWK object
        if crv:
            ccrv = crv
            if ccrv == 'P-256K':
                ccrv = 'secp256k1'
            if ccrv != cname:
                raise InvalidJWKValue('Curve requested is "%s", but '
                                      'key curve is "%s"' % (name, crv))
        kty = self.get('kty')
        if kty is not None and ctype is not None and kty != ctype:
            raise InvalidJWKType('Curve Requested is of type "%s", but '
                                 'key curve is of type "%s"' % (ctype, kty))

        # Return a curve object
        if cname == 'P-256':
            return ec.SECP256R1()
        elif cname == 'P-384':
            return ec.SECP384R1()
        elif cname == 'P-521':
            return ec.SECP521R1()
        elif cname == 'secp256k1':
            return ec.SECP256K1()
        elif cname == 'BP-256':
            return ec.BrainpoolP256R1()
        elif cname == 'BP-384':
            return ec.BrainpoolP384R1()
        elif cname == 'BP-512':
            return ec.BrainpoolP512R1()
        elif cname in _OKP_CURVES_TABLE:
            return _OKP_CURVES_TABLE[cname]
        else:
            raise InvalidJWKValue('Unknown Curve Name [%s]' % (name))

    def _generate_EC(self, params):
        curve = 'P-256'
        if 'curve' in params:
            curve = params.pop('curve')
        # 'curve' is for backwards compat, if 'crv' is defined it takes
        # precedence
        if 'crv' in params:
            curve = params.pop('crv')
        curve_fn = self._get_curve_by_name(curve, 'EC')
        key = ec.generate_private_key(curve_fn, default_backend())
        self._import_pyca_pri_ec(key, **params)

    def _import_pyca_pri_ec(self, key, **params):
        pn = key.private_numbers()
        key_size = pn.public_numbers.curve.key_size
        params.update(
            kty='EC',
            crv=JWKpycaCurveMap[key.curve.name],
            x=self._encode_int(pn.public_numbers.x, key_size),
            y=self._encode_int(pn.public_numbers.y, key_size),
            d=self._encode_int(pn.private_value, key_size)
        )
        self.import_key(**params)

    def _import_pyca_pub_ec(self, key, **params):
        pn = key.public_numbers()
        key_size = pn.curve.key_size
        params.update(
            kty='EC',
            crv=JWKpycaCurveMap[key.curve.name],
            x=self._encode_int(pn.x, key_size),
            y=self._encode_int(pn.y, key_size),
        )
        self.import_key(**params)

    def _generate_OKP(self, params):
        if 'crv' not in params:
            raise InvalidJWKValue('Must specify "crv" for OKP key generation')
        curve_fn = self._get_curve_by_name(params['crv'], 'OKP')
        key = curve_fn.privkey.generate()
        self._import_pyca_pri_okp(key, **params)

    def _okp_curve_from_pyca_key(self, key):
        for name, val in _OKP_CURVES_TABLE.items():
            if isinstance(key, (val.pubkey, val.privkey)):
                return name
        raise InvalidJWKValue('Invalid OKP Key object %r' % key)

    def _import_pyca_pri_okp(self, key, **params):
        params.update(
            kty='OKP',
            crv=self._okp_curve_from_pyca_key(key),
            d=base64url_encode(key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption())),
            x=base64url_encode(key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw))
        )
        self.import_key(**params)

    def _import_pyca_pub_okp(self, key, **params):
        params.update(
            kty='OKP',
            crv=self._okp_curve_from_pyca_key(key),
            x=base64url_encode(key.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw))
        )
        self.import_key(**params)

    def import_key(self, **kwargs):
        newkey = {}
        key_vals = 0
        self._cache_pub_k = None
        self._cache_pri_k = None

        names = list(kwargs.keys())

        for name in list(JWKParamsRegistry.keys()):
            if name in kwargs:
                newkey[name] = kwargs[name]
                while name in names:
                    names.remove(name)

        kty = newkey.get('kty')
        if kty not in JWKTypesRegistry:
            raise InvalidJWKType(kty)

        for name in list(JWKValuesRegistry[kty].keys()):
            if name in kwargs:
                newkey[name] = kwargs[name]
                key_vals += 1
                while name in names:
                    names.remove(name)

        for name, val in JWKValuesRegistry[kty].items():
            if val.required and name not in newkey:
                raise InvalidJWKValue('Missing required value %s' % name)
            if val.type == ParmType.unsupported and name in newkey:
                raise InvalidJWKValue('Unsupported parameter %s' % name)
            if val.type == ParmType.b64 and name in newkey:
                # Check that the value is base64url encoded
                try:
                    base64url_decode(newkey[name])
                except Exception as e:  # pylint: disable=broad-except
                    raise InvalidJWKValue(
                        '"%s" is not base64url encoded' % name
                    ) from e
            if val.type == ParmType.b64u and name in newkey:
                # Check that the value is Base64urlUInt encoded
                try:
                    self._decode_int(newkey[name])
                except Exception as e:  # pylint: disable=broad-except
                    raise InvalidJWKValue(
                        '"%s" is not Base64urlUInt encoded' % name
                    ) from e

        # Unknown key parameters are allowed
        for name in names:
            newkey[name] = kwargs[name]

        if key_vals == 0:
            raise InvalidJWKValue('No Key Values found')

        # check key_ops
        if 'key_ops' in newkey:
            for ko in newkey['key_ops']:
                cnt = 0
                for cko in newkey['key_ops']:
                    if ko == cko:
                        cnt += 1
                if cnt != 1:
                    raise InvalidJWKValue('Duplicate values in "key_ops"')

        # check use/key_ops consistency
        if 'use' in newkey and 'key_ops' in newkey:
            sigl = ['sign', 'verify']
            encl = ['encrypt', 'decrypt', 'wrapKey', 'unwrapKey',
                    'deriveKey', 'deriveBits']
            if newkey['use'] == 'sig':
                for op in encl:
                    if op in newkey['key_ops']:
                        raise InvalidJWKValue('Incompatible "use" and'
                                              ' "key_ops" values specified at'
                                              ' the same time')
            elif newkey['use'] == 'enc':
                for op in sigl:
                    if op in newkey['key_ops']:
                        raise InvalidJWKValue('Incompatible "use" and'
                                              ' "key_ops" values specified at'
                                              ' the same time')

        self.clear()
        # must set 'kty' as first item
        self.__setitem__('kty', newkey['kty'])
        self.update(newkey)

    @classmethod
    def from_json(cls, key):
        """Creates a RFC 7517 JWK from the standard JSON format.

        :param key: The RFC 7517 representation of a JWK.

        :return: A JWK object that holds the json key.
        :rtype: JWK
        """
        obj = cls()
        try:
            jkey = json_decode(key)
        except Exception as e:  # pylint: disable=broad-except
            raise InvalidJWKValue from e
        obj.import_key(**jkey)
        return obj

    def export(self, private_key=True, as_dict=False):
        """Exports the key in the standard JSON format.
        Exports the key regardless of type, if private_key is False
        and the key is_symmetric an exception is raised.

        :param private_key(bool): Whether to export the private key.
                                  Defaults to True.

        :return: A portable representation of the key.
            If as_dict is True then a dictionary is returned.
            By default a json string
        :rtype: `str` or `dict`
        """
        if private_key is True:
            # Use _export_all for backwards compatibility, as this
            # function allows to export symmetric keys too
            return self._export_all(as_dict)

        return self.export_public(as_dict)

    def export_public(self, as_dict=False):
        """Exports the public key in the standard JSON format.
        It fails if one is not available like when this function
        is called on a symmetric key.

        :param as_dict(bool): If set to True export as python dict not JSON

        :return: A portable representation of the public key only.
            If as_dict is True then a dictionary is returned.
            By default a json string
        :rtype: `str` or `dict`
        """
        pub = self._public_params()
        if as_dict is True:
            return pub
        return json_encode(pub)

    def _public_params(self):
        if not self.has_public:
            raise InvalidJWKType("No public key available")
        pub = {}
        reg = JWKParamsRegistry
        for name in reg:
            if reg[name].public:
                if name in self.keys():
                    pub[name] = self.get(name)
        reg = JWKValuesRegistry[self.get('kty')]
        for name in reg:
            if reg[name].public:
                pub[name] = self.get(name)
        return pub

    def _export_all(self, as_dict=False):
        d = {}
        d.update(self)
        if as_dict is True:
            return d
        return json_encode(d)

    def export_private(self, as_dict=False):
        """Export the private key in the standard JSON format.
        It fails for a JWK that has only a public key or is symmetric.

        :param as_dict(bool): If set to True export as python dict not JSON

        :return: A portable representation of a private key.
            If as_dict is True then a dictionary is returned.
            By default a json string
        :rtype: `str` or `dict`
        """
        if self.has_private:
            return self._export_all(as_dict)
        raise InvalidJWKType("No private key available")

    def export_symmetric(self, as_dict=False):
        if self.is_symmetric:
            return self._export_all(as_dict)
        raise InvalidJWKType("Not a symmetric key")

    def public(self):
        pub = self._public_params()
        return JWK(**pub)

    @property
    def has_public(self):
        """Whether this JWK has an asymmetric Public key value."""
        if self.is_symmetric:
            return False
        reg = JWKValuesRegistry[self.get('kty')]
        for name in reg:
            if reg[name].public and name in self.keys():
                return True
        return False

    @property
    def has_private(self):
        """Whether this JWK has an asymmetric Private key value."""
        if self.is_symmetric:
            return False
        reg = JWKValuesRegistry[self.get('kty')]
        for name in reg:
            if not reg[name].public and name in self.keys():
                return True
        return False

    @property
    def is_symmetric(self):
        """Whether this JWK is a symmetric key."""
        return self.get('kty') == 'oct'

    @property
    @deprecated('')
    def key_type(self):
        """The Key type"""
        return self.get('kty')

    @property
    @deprecated('')
    def key_id(self):
        """The Key ID.
        Provided by the kid parameter if present, otherwise returns None.
        """
        return self.get('kid')

    @property
    @deprecated('')
    def key_curve(self):
        """The Curve Name."""
        if self.get('kty') not in ['EC', 'OKP']:
            raise InvalidJWKType('Not an EC or OKP key')
        return self.get('crv')

    @deprecated('')
    def get_curve(self, arg):
        """Gets the Elliptic Curve associated with the key.

        :param arg: an optional curve name

        :raises InvalidJWKType: the key is not an EC or OKP key.
        :raises InvalidJWKValue: if the curve name is invalid.

        :return: An EllipticCurve object
        :rtype: `EllipticCurve`
        """
        return self._get_curve_by_name(arg)

    def _check_constraints(self, usage, operation):
        use = self.get('use')
        if use and use != usage:
            raise InvalidJWKUsage(usage, use)
        ops = self.get('key_ops')
        if ops:
            if not isinstance(ops, list):
                ops = [ops]
            if operation not in ops:
                raise InvalidJWKOperation(operation, ops)
        # TODO: check alg ?

    def _decode_int(self, n):
        return int(hexlify(base64url_decode(n)), 16)

    def _rsa_pub_n(self):
        e = self._decode_int(self.get('e'))
        n = self._decode_int(self.get('n'))
        return rsa.RSAPublicNumbers(e, n)

    def _rsa_pri_n(self):
        p = self._decode_int(self.get('p'))
        q = self._decode_int(self.get('q'))
        d = self._decode_int(self.get('d'))
        dp = self._decode_int(self.get('dp'))
        dq = self._decode_int(self.get('dq'))
        qi = self._decode_int(self.get('qi'))
        return rsa.RSAPrivateNumbers(p, q, d, dp, dq, qi, self._rsa_pub_n())

    def _rsa_pub(self):
        k = self._cache_pub_k
        if k is None:
            k = self._rsa_pub_n().public_key(default_backend())
            self._cache_pub_k = k
        return k

    def _rsa_pri(self):
        k = self._cache_pri_k
        if k is None:
            k = self._rsa_pri_n().private_key(default_backend())
            self._cache_pri_k = k
        return k

    def _ec_pub_n(self, curve):
        x = self._decode_int(self.get('x'))
        y = self._decode_int(self.get('y'))
        curve_fn = self._get_curve_by_name(curve, ctype='EC')
        return ec.EllipticCurvePublicNumbers(x, y, curve_fn)

    def _ec_pri_n(self, curve):
        d = self._decode_int(self.get('d'))
        return ec.EllipticCurvePrivateNumbers(d, self._ec_pub_n(curve))

    def _ec_pub(self, curve):
        k = self._cache_pub_k
        if k is None:
            k = self._ec_pub_n(curve).public_key(default_backend())
            self._cache_pub_k = k
        return k

    def _ec_pri(self, curve):
        k = self._cache_pri_k
        if k is None:
            k = self._ec_pri_n(curve).private_key(default_backend())
            self._cache_pri_k = k
        return k

    def _okp_pub(self):
        k = self._cache_pub_k
        if k is None:
            crv = self.get('crv')
            try:
                pubkey = _OKP_CURVES_TABLE[crv].pubkey
            except KeyError as e:
                raise InvalidJWKValue('Unknown curve "%s"' % crv) from e

            x = base64url_decode(self.get('x'))
            k = pubkey.from_public_bytes(x)
            self._cache_pub_k = k
        return k

    def _okp_pri(self):
        k = self._cache_pri_k
        if k is None:
            crv = self.get('crv')
            try:
                privkey = _OKP_CURVES_TABLE[crv].privkey
            except KeyError as e:
                raise InvalidJWKValue('Unknown curve "%s"' % crv) from e

            d = base64url_decode(self.get('d'))
            k = privkey.from_private_bytes(d)
            self._cache_pri_k = k
        return k

    def _get_public_key(self, arg=None):
        ktype = self.get('kty')
        if ktype == 'oct':
            return self.get('k')
        elif ktype == 'RSA':
            return self._rsa_pub()
        elif ktype == 'EC':
            return self._ec_pub(arg)
        elif ktype == 'OKP':
            return self._okp_pub()
        else:
            raise NotImplementedError

    def _get_private_key(self, arg=None):
        ktype = self.get('kty')
        if ktype == 'oct':
            return self.get('k')
        elif ktype == 'RSA':
            return self._rsa_pri()
        elif ktype == 'EC':
            return self._ec_pri(arg)
        elif ktype == 'OKP':
            return self._okp_pri()
        else:
            raise NotImplementedError

    def get_op_key(self, operation=None, arg=None):
        """Get the key object associated to the requested operation.
        For example the public RSA key for the 'verify' operation or
        the private EC key for the 'decrypt' operation.

        :param operation: The requested operation.
         The valid set of operations is available in the
         :data:`JWKOperationsRegistry` registry.
        :param arg: An optional, context specific, argument.
         For example a curve name.

        :raises InvalidJWKOperation: if the operation is unknown or
         not permitted with this key.
        :raises InvalidJWKUsage: if the use constraints do not permit
         the operation.

        :return: A Python Cryptography key object for asymmetric keys
            or a baseurl64_encoded octet string for symmetric keys
        """
        validops = self.get('key_ops',
                            list(JWKOperationsRegistry.keys()))
        if validops is not list:
            validops = [validops]
        if operation is None:
            if self.get('kty') == 'oct':
                return self.get('k')
            raise InvalidJWKOperation(operation, validops)
        elif operation == 'sign':
            self._check_constraints('sig', operation)
            return self._get_private_key(arg)
        elif operation == 'verify':
            self._check_constraints('sig', operation)
            return self._get_public_key(arg)
        elif operation == 'encrypt' or operation == 'wrapKey':
            self._check_constraints('enc', operation)
            return self._get_public_key(arg)
        elif operation == 'decrypt' or operation == 'unwrapKey':
            self._check_constraints('enc', operation)
            return self._get_private_key(arg)
        else:
            raise NotImplementedError

    def import_from_pyca(self, key):
        if isinstance(key, rsa.RSAPrivateKey):
            self._import_pyca_pri_rsa(key)
        elif isinstance(key, rsa.RSAPublicKey):
            self._import_pyca_pub_rsa(key)
        elif isinstance(key, ec.EllipticCurvePrivateKey):
            self._import_pyca_pri_ec(key)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            self._import_pyca_pub_ec(key)
        elif isinstance(key, (Ed25519PrivateKey,
                              Ed448PrivateKey,
                              X25519PrivateKey)):
            self._import_pyca_pri_okp(key)
        elif isinstance(key, (Ed25519PublicKey,
                              Ed448PublicKey,
                              X25519PublicKey)):
            self._import_pyca_pub_okp(key)
        else:
            raise InvalidJWKValue('Unknown key object %r' % key)

    def import_from_pem(self, data, password=None, kid=None):
        """Imports a key from data loaded from a PEM file.
        The key may be encrypted with a password.
        Private keys (PKCS#8 format), public keys, and X509 certificate's
        public keys can be imported with this interface.

        :param data(bytes): The data contained in a PEM file.
        :param password(bytes): An optional password to unwrap the key.
        """

        try:
            key = serialization.load_pem_private_key(
                data, password=password, backend=default_backend())
        except ValueError as e:
            if password is not None:
                raise e
            try:
                key = serialization.load_pem_public_key(
                    data, backend=default_backend())
            except ValueError:
                try:
                    cert = x509.load_pem_x509_certificate(
                        data, backend=default_backend())
                    key = cert.public_key()
                except ValueError:
                    # pylint: disable=raise-missing-from
                    raise e

        self.import_from_pyca(key)
        if kid is None:
            kid = self.thumbprint()
        self.__setitem__('kid', kid)

    def export_to_pem(self, private_key=False, password=False):
        """Exports keys to a data buffer suitable to be stored as a PEM file.
        Either the public or the private key can be exported to a PEM file.
        For private keys the PKCS#8 format is used. If a password is provided
        the best encryption method available as determined by the cryptography
        module is used to wrap the key.

        :param private_key: Whether the private key should be exported.
         Defaults to `False` which means the public key is exported by default.
        :param password(bytes): A password for wrapping the private key.
         Defaults to False which will cause the operation to fail. To avoid
         encryption the user must explicitly pass None, otherwise the user
         needs to provide a password in a bytes buffer.

        :return: A serialized bytes buffer containing a PEM formatted key.
        :rtype: `bytes`
        """
        enc = serialization.Encoding.PEM
        if private_key:
            if not self.has_private:
                raise InvalidJWKType("No private key available")
            f = serialization.PrivateFormat.PKCS8
            if password is None:
                enc_alg = serialization.NoEncryption()
            elif isinstance(password, bytes):
                enc_alg = serialization.BestAvailableEncryption(password)
            elif password is False:
                raise ValueError("The password must be None or a bytes string")
            else:
                raise TypeError("The password string must be bytes")
            return self._get_private_key().private_bytes(
                encoding=enc, format=f, encryption_algorithm=enc_alg)
        else:
            if not self.has_public:
                raise InvalidJWKType("No public key available")
            f = serialization.PublicFormat.SubjectPublicKeyInfo
            return self._get_public_key().public_bytes(encoding=enc, format=f)

    @classmethod
    def from_pyca(cls, key):
        obj = cls()
        obj.import_from_pyca(key)
        return obj

    @classmethod
    def from_pem(cls, data, password=None):
        """Creates a key from PKCS#8 formatted data loaded from a PEM file.
           See the function `import_from_pem` for details.

        :param data(bytes): The data contained in a PEM file.
        :param password(bytes): An optional password to unwrap the key.

        :return: A JWK object.
        :rtype: JWK
        """
        obj = cls()
        obj.import_from_pem(data, password)
        return obj

    def thumbprint(self, hashalg=hashes.SHA256()):
        """Returns the key thumbprint as specified by RFC 7638.

        :param hashalg: A hash function (defaults to SHA256)

        :return: A base64url encoded digest of the key
        :rtype: `str`
        """

        t = {'kty': self.get('kty')}
        for name, val in JWKValuesRegistry[t['kty']].items():
            if val.required:
                t[name] = self.get(name)
        digest = hashes.Hash(hashalg, backend=default_backend())
        digest.update(bytes(json_encode(t).encode('utf8')))
        return base64url_encode(digest.finalize())

    def thumbprint_uri(self, hname='sha-256'):
        """Returns the key thumbprint URI as specified by RFC 9278.

        :param hname: A hash function name as specified in IANA's
         Named Information registry:
         https://www.iana.org/assignments/named-information/
         Values from `IANANamedInformationHashAlgorithmRegistry`

        :return: A JWK Thumbprint URI
        :rtype: `str`
        """

        try:
            h = IANANamedInformationHashAlgorithmRegistry[hname]
        except KeyError as e:
            raise InvalidJWKValue('Unknown hash "{}"'.format(hname)) from e
        if h is None:
            raise InvalidJWKValue('Unsupported hash "{}"'.format(hname))

        t = self.thumbprint(h)
        return "urn:ietf:params:oauth:jwk-thumbprint:{}:{}".format(hname, t)

    # Methods to constrain what this dict allows
    def __setitem__(self, item, value):
        kty = self.get('kty')

        if item == 'kty':
            if kty is None:
                if value not in JWKTypesRegistry:
                    raise InvalidJWKType(value)
                super(JWK, self).__setitem__(item, value)
                return
            elif kty != value:
                raise ValueError('Cannot change key type')

        # Check if item is a key value and verify its format
        if item in list(JWKValuesRegistry[kty].keys()):
            # Invalidate cached keys if any
            self._cache_pub_k = None
            self._cache_pri_k = None
            if JWKValuesRegistry[kty][item].type == ParmType.b64:
                try:
                    v = base64url_decode(value)
                    # empty values are also invalid except for the
                    # special case of 'oct' key where an empty value
                    # is used to indicate a 'None' key
                    if v == b'' and kty != 'oct' and item != 'k':
                        raise ValueError
                except Exception as e:  # pylint: disable=broad-except
                    raise InvalidJWKValue(
                        '"%s" is not base64url encoded' % item
                    ) from e
            elif JWKValuesRegistry[kty][item].type == ParmType.b64u:
                try:
                    self._decode_int(value)
                except Exception as e:  # pylint: disable=broad-except
                    raise InvalidJWKValue(
                        '"%s" is not Base64urlUInt encoded' % item
                    ) from e
            super(JWK, self).__setitem__(item, value)
            return

        # If not a key param check if it is a know parameter
        if item in list(JWKParamsRegistry.keys()):
            super(JWK, self).__setitem__(item, value)
            return

        # if neither a key param nor a known parameter, check if we are
        # trying to set a parameter for a different key type and refuse
        # in this case.
        for name in list(JWKTypesRegistry.keys()):
            if name == kty:
                continue
            if item in list(JWKValuesRegistry[name].keys()):
                raise KeyError("Cannot set '{}' on '{}' key type".format(
                               item, kty))

        # ok if we've come this far it means we have an unknown parameter
        super(JWK, self).__setitem__(item, value)

    def update(self, *args, **kwargs):
        r"""
        :param \*args: arguments
        :param \**kwargs: keyword arguments
        """
        for k, v in dict(*args, **kwargs).items():
            self.__setitem__(k, v)

    def setdefault(self, key, default=None):
        if key not in self.keys():
            self.__setitem__(key, default)
        return self.get(key)

    def __delitem__(self, item):
        param = self.get(item)
        if param is None:
            raise KeyError(item)

        if item == 'kty':
            for name in list(JWKValuesRegistry[param].keys()):
                if self.get(name) is not None:
                    raise KeyError("Cannot remove 'kty', values present")

        kty = self.get('kty')
        if kty is not None and item in list(JWKValuesRegistry[kty].keys()):
            # Invalidate cached keys if any
            self._cache_pub_k = None
            self._cache_pri_k = None

        super(JWK, self).__delitem__(item)

    def __eq__(self, other):
        if not isinstance(other, JWK):
            return NotImplemented

        return self.thumbprint() == other.thumbprint() and \
            self.get('kid') == other.get('kid')

    def __hash__(self):
        return hash((self.thumbprint(), self.get('kid')))

    def __getattr__(self, item):
        try:
            if item in JWKParamsRegistry.keys():
                if item in self.keys():
                    return self.get(item)
            kty = self.get('kty')
            if kty is not None:
                if item in list(JWKValuesRegistry[kty].keys()):
                    if item in self.keys():
                        return self.get(item)
            raise KeyError
        except KeyError:
            raise AttributeError(item) from None

    def __setattr__(self, item, value):
        try:
            if item in JWKParamsRegistry.keys():
                self.__setitem__(item, value)
            for name in list(JWKTypesRegistry.keys()):
                if item in list(JWKValuesRegistry[name].keys()):
                    self.__setitem__(item, value)
            super(JWK, self).__setattr__(item, value)
        except KeyError:
            raise AttributeError(item) from None

    @classmethod
    def from_password(cls, password):
        """Creates a symmetric JWK key from a user password.

        :param password: A password in utf8 format.

        :return: a JWK object
        :rtype: JWK
        """
        obj = cls()
        params = {'kty': 'oct'}
        try:
            params['k'] = base64url_encode(password.encode('utf8'))
        except Exception as e:  # pylint: disable=broad-except
            raise InvalidJWKValue from e
        obj.import_key(**params)
        return obj

    # Prevent accidental disclosure of key material via repr()
    def __repr__(self):
        repr_dict = {}
        repr_dict['kid'] = self.get('kid', 'Missing Key ID')
        repr_dict['thumbprint'] = self.thumbprint()
        return json_encode(repr_dict)


class _JWKkeys(set):

    def add(self, elem):
        """Adds a JWK object to the set

        :param elem: the JWK object to add.

        :raises TypeError: if the object is not a JWK.
        """
        if not isinstance(elem, JWK):
            raise TypeError('Only JWK objects are valid elements')
        set.add(self, elem)


class JWKSet(dict):
    """A set of JWK objects.

    Inherits from the standard 'dict' builtin type.
    Creates a special key 'keys' that is of a type derived from 'set'
    The 'keys' attribute accepts only :class:`jwcrypto.jwk.JWK` elements.
    """

    def __init__(self, *args, **kwargs):
        super(JWKSet, self).__init__()
        super(JWKSet, self).__setitem__('keys', _JWKkeys())
        self.update(*args, **kwargs)

    def __iter__(self):
        return self['keys'].__iter__()

    def __contains__(self, key):
        return self['keys'].__contains__(key)

    def __setitem__(self, key, val):
        if key == 'keys' and not isinstance(val, _JWKkeys):
            self['keys'].add(val)
        else:
            super(JWKSet, self).__setitem__(key, val)

    def update(self, *args, **kwargs):
        r"""
        :param \*args: arguments
        :param \**kwargs: keyword arguments
        """
        for k, v in dict(*args, **kwargs).items():
            self.__setitem__(k, v)

    def setdefault(self, key, default=None):
        if key not in self.keys():
            self.__setitem__(key, default)
        return self.get(key)

    def add(self, elem):
        self['keys'].add(elem)

    def export(self, private_keys=True, as_dict=False):
        """Exports a RFC 7517 key set.
           Exports as json by default, or as dict if requested.

        :param private_key(bool): Whether to export private keys.
                                  Defaults to True.
        :param as_dict(bool): Whether to return a dict instead of
                              a JSON object

        :return: A portable representation of the key set.
            If as_dict is True then a dictionary is returned.
            By default a json string
        :rtype: `str` or `dict`
        """
        exp_dict = {}
        for k, v in self.items():
            if k == 'keys':
                keys = []
                for jwk in v:
                    keys.append(jwk.export(private_keys, as_dict=True))
                v = keys
            exp_dict[k] = v
        if as_dict is True:
            return exp_dict
        return json_encode(exp_dict)

    def import_keyset(self, keyset):
        """Imports a RFC 7517 key set using the standard JSON format.

        :param keyset: The RFC 7517 representation of a JOSE key set.
        """
        try:
            jwkset = json_decode(keyset)
        except Exception as e:  # pylint: disable=broad-except
            raise InvalidJWKValue from e

        if 'keys' not in jwkset:
            raise InvalidJWKValue

        for k, v in jwkset.items():
            if k == 'keys':
                for jwk in v:
                    self['keys'].add(JWK(**jwk))
            else:
                self[k] = v

    @classmethod
    def from_json(cls, keyset):
        """Creates a RFC 7517 key set from the standard JSON format.

        :param keyset: The RFC 7517 representation of a JOSE key set.

        :return: A JWKSet object.
        :rtype: JWKSet
        """
        obj = cls()
        obj.import_keyset(keyset)
        return obj

    def get_key(self, kid):
        """Gets a key from the set.
        :param kid: the 'kid' key identifier.

        :return: A JWK from the set
        :rtype: JWK
        """
        keys = self.get_keys(kid)
        if len(keys) > 1:
            raise InvalidJWKValue(
                'Duplicate keys found with requested kid: 1 expected')
        try:
            return tuple(keys)[0]
        except IndexError:
            return None

    def get_keys(self, kid):
        """Gets keys from the set with matching kid.
        :param kid: the 'kid' key identifier.

        :return: a List of keys
        :rtype: `list`
        """
        return {key for key in self['keys'] if key.get('kid') == kid}

    def __repr__(self):
        repr_dict = {}
        for k, v in self.items():
            if k == 'keys':
                keys = []
                for jwk in v:
                    keys.append(repr(jwk))
                v = keys
            repr_dict[k] = v
        return json_encode(repr_dict)
