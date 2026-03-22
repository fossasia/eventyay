# Copyright (C) 2015 JWCrypto Project Contributors - see LICENSE file

import zlib

from jwcrypto import common
from jwcrypto.common import JWException, JWKeyNotFound
from jwcrypto.common import JWSEHeaderParameter, JWSEHeaderRegistry
from jwcrypto.common import base64url_decode, base64url_encode
from jwcrypto.common import json_decode, json_encode
from jwcrypto.jwa import JWA
from jwcrypto.jwk import JWKSet

# Limit the amount of data we are willing to decompress by default.
default_max_compressed_size = 256 * 1024


# RFC 7516 - 4.1
# name: (description, supported?)
JWEHeaderRegistry = {
    'alg': JWSEHeaderParameter('Algorithm', False, True, None),
    'enc': JWSEHeaderParameter('Encryption Algorithm', False, True, None),
    'zip': JWSEHeaderParameter('Compression Algorithm', False, True, None),
    'jku': JWSEHeaderParameter('JWK Set URL', False, False, None),
    'jwk': JWSEHeaderParameter('JSON Web Key', False, False, None),
    'kid': JWSEHeaderParameter('Key ID', False, True, None),
    'x5u': JWSEHeaderParameter('X.509 URL', False, False, None),
    'x5c': JWSEHeaderParameter('X.509 Certificate Chain', False, False, None),
    'x5t': JWSEHeaderParameter('X.509 Certificate SHA-1 Thumbprint', False,
                               False, None),
    'x5t#S256': JWSEHeaderParameter('X.509 Certificate SHA-256 Thumbprint',
                                    False, False, None),
    'typ': JWSEHeaderParameter('Type', False, True, None),
    'cty': JWSEHeaderParameter('Content Type', False, True, None),
    'crit': JWSEHeaderParameter('Critical', True, True, None),
}
"""Registry of valid header parameters"""

default_allowed_algs = [
    # Key Management Algorithms
    'RSA-OAEP', 'RSA-OAEP-256',
    'A128KW', 'A192KW', 'A256KW',
    'dir',
    'ECDH-ES', 'ECDH-ES+A128KW', 'ECDH-ES+A192KW', 'ECDH-ES+A256KW',
    'A128GCMKW', 'A192GCMKW', 'A256GCMKW',
    'PBES2-HS256+A128KW', 'PBES2-HS384+A192KW', 'PBES2-HS512+A256KW',
    # Content Encryption Algorithms
    'A128CBC-HS256', 'A192CBC-HS384', 'A256CBC-HS512',
    'A128GCM', 'A192GCM', 'A256GCM']
"""Default allowed algorithms"""


class InvalidJWEData(JWException):
    """Invalid JWE Object.

    This exception is raised when the JWE Object is invalid and/or
    improperly formatted.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = message
        else:
            msg = 'Unknown Data Verification Failure'
        if exception:
            msg += ' {%s}' % str(exception)
        super(InvalidJWEData, self).__init__(msg)


# These have been moved to jwcrypto.common, maintain here for backwards compat
InvalidCEKeyLength = common.InvalidCEKeyLength
InvalidJWEKeyLength = common.InvalidJWEKeyLength
InvalidJWEKeyType = common.InvalidJWEKeyType
InvalidJWEOperation = common.InvalidJWEOperation


class JWE:
    """JSON Web Encryption object

    This object represent a JWE token.
    """

    def __init__(self, plaintext=None, protected=None, unprotected=None,
                 aad=None, algs=None, recipient=None, header=None,
                 header_registry=None):
        """Creates a JWE token.

        :param plaintext(bytes): An arbitrary plaintext to be encrypted.
        :param protected: A JSON string with the protected header.
        :param unprotected: A JSON string with the shared unprotected header.
        :param aad(bytes): Arbitrary additional authenticated data
        :param algs: An optional list of allowed algorithms
        :param recipient: An optional, default recipient key
        :param header: An optional header for the default recipient
        :param header_registry: Optional additions to the header registry
        """
        self._allowed_algs = None
        self.objects = {}
        self.plaintext = None
        self.header_registry = JWSEHeaderRegistry(JWEHeaderRegistry)
        if header_registry:
            self.header_registry.update(header_registry)
        if plaintext is not None:
            if isinstance(plaintext, bytes):
                self.plaintext = plaintext
            else:
                self.plaintext = plaintext.encode('utf-8')
        self.cek = None
        self.decryptlog = None
        if aad:
            self.objects['aad'] = aad
        if protected:
            if isinstance(protected, dict):
                protected = json_encode(protected)
            else:
                json_decode(protected)  # check header encoding
            self.objects['protected'] = protected
        if unprotected:
            if isinstance(unprotected, dict):
                unprotected = json_encode(unprotected)
            else:
                json_decode(unprotected)  # check header encoding
            self.objects['unprotected'] = unprotected
        if algs:
            self._allowed_algs = algs

        if recipient:
            self.add_recipient(recipient, header=header)
        elif header:
            raise ValueError('Header is allowed only with default recipient')

    def _jwa_keymgmt(self, name):
        allowed = self._allowed_algs or default_allowed_algs
        if name not in allowed:
            raise InvalidJWEOperation('Algorithm not allowed')
        return JWA.keymgmt_alg(name)

    def _jwa_enc(self, name):
        allowed = self._allowed_algs or default_allowed_algs
        if name not in allowed:
            raise InvalidJWEOperation('Algorithm not allowed')
        return JWA.encryption_alg(name)

    @property
    def allowed_algs(self):
        """Allowed algorithms.

        The list of allowed algorithms.
        Can be changed by setting a list of algorithm names.
        """

        if self._allowed_algs:
            return self._allowed_algs
        else:
            return default_allowed_algs

    @allowed_algs.setter
    def allowed_algs(self, algs):
        if not isinstance(algs, list):
            raise TypeError('Allowed Algs must be a list')
        self._allowed_algs = algs

    def _merge_headers(self, h1, h2):
        for k in list(h1.keys()):
            if k in h2:
                raise InvalidJWEData('Duplicate header: "%s"' % k)
        h1.update(h2)
        return h1

    def _get_jose_header(self, header=None):
        jh = {}
        if 'protected' in self.objects:
            ph = json_decode(self.objects['protected'])
            jh = self._merge_headers(jh, ph)
        if 'unprotected' in self.objects:
            uh = json_decode(self.objects['unprotected'])
            jh = self._merge_headers(jh, uh)
        if header:
            rh = json_decode(header)
            jh = self._merge_headers(jh, rh)
        return jh

    def _get_alg_enc_from_headers(self, jh):
        algname = jh.get('alg', None)
        if algname is None:
            raise InvalidJWEData('Missing "alg" from headers')
        alg = self._jwa_keymgmt(algname)
        encname = jh.get('enc', None)
        if encname is None:
            raise InvalidJWEData('Missing "enc" from headers')
        enc = self._jwa_enc(encname)
        return alg, enc

    def _encrypt(self, alg, enc, jh):
        aad = base64url_encode(self.objects.get('protected', ''))
        if 'aad' in self.objects:
            aad += '.' + base64url_encode(self.objects['aad'])
        aad = aad.encode('utf-8')

        compress = jh.get('zip', None)
        if compress == 'DEF':
            data = zlib.compress(self.plaintext)[2:-4]
        elif compress is None:
            data = self.plaintext
        else:
            raise ValueError('Unknown compression')

        iv, ciphertext, tag = enc.encrypt(self.cek, aad, data)
        self.objects['iv'] = iv
        self.objects['ciphertext'] = ciphertext
        self.objects['tag'] = tag

    def add_recipient(self, key, header=None):
        """Encrypt the plaintext with the given key.

        :param key: A JWK key or password of appropriate type for the 'alg'
         provided in the JOSE Headers.
        :param header: A JSON string representing the per-recipient header.

        :raises ValueError: if the plaintext is missing or not of type bytes.
        :raises ValueError: if the compression type is unknown.
        :raises InvalidJWAAlgorithm: if the 'alg' provided in the JOSE
         headers is missing or unknown, or otherwise not implemented.
        """
        if self.plaintext is None:
            raise ValueError('Missing plaintext')
        if not isinstance(self.plaintext, bytes):
            raise ValueError("Plaintext must be 'bytes'")

        if isinstance(header, dict):
            header = json_encode(header)

        jh = self._get_jose_header(header)
        alg, enc = self._get_alg_enc_from_headers(jh)

        rec = {}
        if header:
            rec['header'] = header

        wrapped = alg.wrap(key, enc.wrap_key_size, self.cek, jh)
        self.cek = wrapped['cek']

        if 'ek' in wrapped:
            rec['encrypted_key'] = wrapped['ek']

        if 'header' in wrapped:
            h = json_decode(rec.get('header', '{}'))
            nh = self._merge_headers(h, wrapped['header'])
            rec['header'] = json_encode(nh)

        if 'ciphertext' not in self.objects:
            self._encrypt(alg, enc, jh)

        if 'recipients' in self.objects:
            self.objects['recipients'].append(rec)
        elif 'encrypted_key' in self.objects or 'header' in self.objects:
            self.objects['recipients'] = []
            n = {}
            if 'encrypted_key' in self.objects:
                n['encrypted_key'] = self.objects.pop('encrypted_key')
            if 'header' in self.objects:
                n['header'] = self.objects.pop('header')
            self.objects['recipients'].append(n)
            self.objects['recipients'].append(rec)
        else:
            self.objects.update(rec)

    def serialize(self, compact=False):
        """Serializes the object into a JWE token.

        :param compact(boolean): if True generates the compact
         representation, otherwise generates a standard JSON format.

        :raises InvalidJWEOperation: if the object cannot be serialized
         with the compact representation and `compact` is True.
        :raises InvalidJWEOperation: if no recipients have been added
         to the object.

        :return: A json formatted string or a compact representation string
        :rtype: `str`
        """

        if 'ciphertext' not in self.objects:
            raise InvalidJWEOperation("No available ciphertext")

        if compact:
            for invalid in 'aad', 'unprotected':
                if invalid in self.objects:
                    raise InvalidJWEOperation(
                        "Can't use compact encoding when the '%s' parameter "
                        "is set" % invalid)
            if 'protected' not in self.objects:
                raise InvalidJWEOperation(
                    "Can't use compact encoding without protected headers")
            else:
                ph = json_decode(self.objects['protected'])
                for required in 'alg', 'enc':
                    if required not in ph:
                        raise InvalidJWEOperation(
                            "Can't use compact encoding, '%s' must be in the "
                            "protected header" % required)
            if 'recipients' in self.objects:
                if len(self.objects['recipients']) != 1:
                    raise InvalidJWEOperation("Invalid number of recipients")
                rec = self.objects['recipients'][0]
            else:
                rec = self.objects
            if 'header' in rec:
                # The AESGCMKW algorithm generates data (iv, tag) we put in the
                # per-recipient unprotected header by default. Move it to the
                # protected header and re-encrypt the payload, as the protected
                # header is used as additional authenticated data.
                h = json_decode(rec['header'])
                ph = json_decode(self.objects['protected'])
                nph = self._merge_headers(h, ph)
                self.objects['protected'] = json_encode(nph)
                jh = self._get_jose_header()
                alg, enc = self._get_alg_enc_from_headers(jh)
                self._encrypt(alg, enc, jh)
                del rec['header']

            return '.'.join([base64url_encode(self.objects['protected']),
                             base64url_encode(rec.get('encrypted_key', '')),
                             base64url_encode(self.objects['iv']),
                             base64url_encode(self.objects['ciphertext']),
                             base64url_encode(self.objects['tag'])])
        else:
            obj = self.objects
            enc = {'ciphertext': base64url_encode(obj['ciphertext']),
                   'iv': base64url_encode(obj['iv']),
                   'tag': base64url_encode(self.objects['tag'])}
            if 'protected' in obj:
                enc['protected'] = base64url_encode(obj['protected'])
            if 'unprotected' in obj:
                enc['unprotected'] = json_decode(obj['unprotected'])
            if 'aad' in obj:
                enc['aad'] = base64url_encode(obj['aad'])
            if 'recipients' in obj:
                enc['recipients'] = []
                for rec in obj['recipients']:
                    e = {}
                    if 'encrypted_key' in rec:
                        e['encrypted_key'] = \
                            base64url_encode(rec['encrypted_key'])
                    if 'header' in rec:
                        e['header'] = json_decode(rec['header'])
                    enc['recipients'].append(e)
            else:
                if 'encrypted_key' in obj:
                    enc['encrypted_key'] = \
                        base64url_encode(obj['encrypted_key'])
                if 'header' in obj:
                    enc['header'] = json_decode(obj['header'])
            return json_encode(enc)

    def _check_crit(self, crit):
        for k in crit:
            if k not in self.header_registry:
                raise InvalidJWEData('Unknown critical header: "%s"' % k)
            else:
                if not self.header_registry[k].supported:
                    raise InvalidJWEData('Unsupported critical header: '
                                         '"%s"' % k)

    def _unwrap_decrypt(self, alg, enc, key, enckey, header,
                        aad, iv, ciphertext, tag):
        cek = alg.unwrap(key, enc.wrap_key_size, enckey, header)
        data = enc.decrypt(cek, aad, iv, ciphertext, tag)
        self.decryptlog.append('Success')
        self.cek = cek
        return data

    # FIXME: allow to specify which algorithms to accept as valid
    def _decrypt(self, key, ppe):

        jh = self._get_jose_header(ppe.get('header', None))

        # TODO: allow caller to specify list of headers it understands
        self._check_crit(jh.get('crit', {}))

        for hdr in jh:
            if hdr in self.header_registry:
                if not self.header_registry.check_header(hdr, self):
                    raise InvalidJWEData('Failed header check')

        alg = self._jwa_keymgmt(jh.get('alg', None))
        enc = self._jwa_enc(jh.get('enc', None))

        aad = base64url_encode(self.objects.get('protected', ''))
        if 'aad' in self.objects:
            aad += '.' + base64url_encode(self.objects['aad'])
        aad = aad.encode('utf-8')

        if isinstance(key, JWKSet):
            keys = key
            if 'kid' in self.jose_header:
                kid_keys = key.get_keys(self.jose_header['kid'])
                if not kid_keys:
                    raise JWKeyNotFound('Key ID {} not in key set'.format(
                                        self.jose_header['kid']))
                keys = kid_keys

            for k in keys:
                try:
                    data = self._unwrap_decrypt(alg, enc, k,
                                                ppe.get('encrypted_key', b''),
                                                jh, aad, self.objects['iv'],
                                                self.objects['ciphertext'],
                                                self.objects['tag'])
                    self.decryptlog.append("Success")
                    break
                except Exception as e:  # pylint: disable=broad-except
                    keyid = k.get('kid', k.thumbprint())
                    self.decryptlog.append('Key [{}] failed: [{}]'.format(
                                           keyid, repr(e)))

            if "Success" not in self.decryptlog:
                raise JWKeyNotFound('No working key found in key set')
        else:
            data = self._unwrap_decrypt(alg, enc, key,
                                        ppe.get('encrypted_key', b''),
                                        jh, aad, self.objects['iv'],
                                        self.objects['ciphertext'],
                                        self.objects['tag'])

        compress = jh.get('zip', None)
        if compress == 'DEF':
            if len(data) > default_max_compressed_size:
                raise InvalidJWEData(
                    'Compressed data exceeds maximum allowed'
                    'size' + f' ({default_max_compressed_size})')
            self.plaintext = zlib.decompress(data, -zlib.MAX_WBITS)
        elif compress is None:
            self.plaintext = data
        else:
            raise ValueError('Unknown compression')

    def decrypt(self, key):
        """Decrypt a JWE token.

        :param key: The (:class:`jwcrypto.jwk.JWK`) decryption key.
        :param key: A (:class:`jwcrypto.jwk.JWK`) decryption key,
         or a (:class:`jwcrypto.jwk.JWKSet`) that contains a key indexed
         by the 'kid' header or (deprecated) a string containing a password.

        :raises InvalidJWEOperation: if the key is not a JWK object.
        :raises InvalidJWEData: if the ciphertext can't be decrypted or
         the object is otherwise malformed.
        :raises JWKeyNotFound: if key is a JWKSet and the key is not found.
        """

        if 'ciphertext' not in self.objects:
            raise InvalidJWEOperation("No available ciphertext")
        self.decryptlog = []
        missingkey = False

        if 'recipients' in self.objects:
            for rec in self.objects['recipients']:
                try:
                    self._decrypt(key, rec)
                except Exception as e:  # pylint: disable=broad-except
                    if isinstance(e, JWKeyNotFound):
                        missingkey = True
                    self.decryptlog.append('Failed: [%s]' % repr(e))
        else:
            try:
                self._decrypt(key, self.objects)
            except Exception as e:  # pylint: disable=broad-except
                if isinstance(e, JWKeyNotFound):
                    missingkey = True
                self.decryptlog.append('Failed: [%s]' % repr(e))

        if not self.plaintext:
            if missingkey:
                raise JWKeyNotFound("Key Not found in JWKSet")
            raise InvalidJWEData('No recipient matched the provided '
                                 'key' + repr(self.decryptlog))

    def deserialize(self, raw_jwe, key=None):
        """Deserialize a JWE token.

        NOTE: Destroys any current status and tries to import the raw
        JWE provided.

        If a key is provided a decryption step will be attempted after
        the object is successfully deserialized.

        :param raw_jwe: a 'raw' JWE token (JSON Encoded or Compact
         notation) string.
        :param key: A (:class:`jwcrypto.jwk.JWK`) decryption key,
         or a (:class:`jwcrypto.jwk.JWKSet`) that contains a key indexed
         by the 'kid' header or (deprecated) a string containing a password
         (optional).

        :raises InvalidJWEData: if the raw object is an invalid JWE token.
        :raises InvalidJWEOperation: if the decryption fails.
        """

        self.objects = {}
        self.plaintext = None
        self.cek = None

        o = {}
        try:
            try:
                djwe = json_decode(raw_jwe)
                o['iv'] = base64url_decode(djwe['iv'])
                o['ciphertext'] = base64url_decode(djwe['ciphertext'])
                o['tag'] = base64url_decode(djwe['tag'])
                if 'protected' in djwe:
                    p = base64url_decode(djwe['protected'])
                    o['protected'] = p.decode('utf-8')
                if 'unprotected' in djwe:
                    o['unprotected'] = json_encode(djwe['unprotected'])
                if 'aad' in djwe:
                    o['aad'] = base64url_decode(djwe['aad'])
                if 'recipients' in djwe:
                    o['recipients'] = []
                    for rec in djwe['recipients']:
                        e = {}
                        if 'encrypted_key' in rec:
                            e['encrypted_key'] = \
                                base64url_decode(rec['encrypted_key'])
                        if 'header' in rec:
                            e['header'] = json_encode(rec['header'])
                        o['recipients'].append(e)
                else:
                    if 'encrypted_key' in djwe:
                        o['encrypted_key'] = \
                            base64url_decode(djwe['encrypted_key'])
                    if 'header' in djwe:
                        o['header'] = json_encode(djwe['header'])

            except ValueError as e:
                data = raw_jwe.split('.')
                if len(data) != 5:
                    raise InvalidJWEData() from e
                p = base64url_decode(data[0])
                o['protected'] = p.decode('utf-8')
                ekey = base64url_decode(data[1])
                if ekey != b'':
                    o['encrypted_key'] = base64url_decode(data[1])
                o['iv'] = base64url_decode(data[2])
                o['ciphertext'] = base64url_decode(data[3])
                o['tag'] = base64url_decode(data[4])

            self.objects = o

        except Exception as e:  # pylint: disable=broad-except
            raise InvalidJWEData('Invalid format', repr(e)) from e

        if key:
            self.decrypt(key)

    @property
    def payload(self):
        if not self.plaintext:
            raise InvalidJWEOperation("Plaintext not available")
        return self.plaintext

    @property
    def jose_header(self):
        jh = self._get_jose_header(self.objects.get('header'))
        if len(jh) == 0:
            raise InvalidJWEOperation("JOSE Header not available")
        return jh

    @classmethod
    def from_jose_token(cls, token):
        """Creates a JWE object from a serialized JWE token.

        :param token: A string with the json or compat representation
         of the token.

        :raises InvalidJWEData: if the raw object is an invalid JWE token.

        :return: A JWE token
        :rtype: JWE
        """

        obj = cls()
        obj.deserialize(token)
        return obj

    def __eq__(self, other):
        if not isinstance(other, JWE):
            return False
        try:
            return self.serialize() == other.serialize()
        except Exception:  # pylint: disable=broad-except
            data1 = {'plaintext': self.plaintext}
            data1.update(self.objects)
            data2 = {'plaintext': other.plaintext}
            data2.update(other.objects)
            return data1 == data2

    def __str__(self):
        try:
            return self.serialize()
        except Exception:  # pylint: disable=broad-except
            return self.__repr__()

    def __repr__(self):
        try:
            return f'JWE.from_json_token("{self.serialize()}")'
        except Exception:  # pylint: disable=broad-except
            plaintext = repr(self.plaintext)
            protected = self.objects.get('protected')
            unprotected = self.objects.get('unprotected')
            aad = self.objects.get('aad')
            algs = self._allowed_algs
            return f'JWE(plaintext={plaintext}, ' + \
                   f'protected={protected}, ' + \
                   f'unprotected={unprotected}, ' + \
                   f'aad={aad}, algs={algs})'
