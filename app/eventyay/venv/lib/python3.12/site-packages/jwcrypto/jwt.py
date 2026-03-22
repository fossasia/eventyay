# Copyright (C) 2015  JWCrypto Project Contributors - see LICENSE file

import copy
import time
import uuid

from typing_extensions import deprecated

from jwcrypto.common import JWException, JWKeyNotFound
from jwcrypto.common import json_decode, json_encode
from jwcrypto.jwe import JWE
from jwcrypto.jwe import default_allowed_algs as jwe_algs
from jwcrypto.jwk import JWK, JWKSet
from jwcrypto.jws import JWS
from jwcrypto.jws import default_allowed_algs as jws_algs


# RFC 7519 - 4.1
# name: description
JWTClaimsRegistry = {'iss': 'Issuer',
                     'sub': 'Subject',
                     'aud': 'Audience',
                     'exp': 'Expiration Time',
                     'nbf': 'Not Before',
                     'iat': 'Issued At',
                     'jti': 'JWT ID'}
"""Registry of RFC 7519 defined claims"""


# do not use this unless you know about CVE-2022-3102
JWT_expect_type = True
"""This module parameter can disable the use of the expectation
   feature that has been introduced to fix CVE-2022-3102. This knob
   has been added as a workaround for applications that can't be
   immediately refactored to deal with the change in behavior but it
   is considered deprecated and will be removed in a future release.
"""


class JWTExpired(JWException):
    """JSON Web Token is expired.

    This exception is raised when a token is expired according to its claims.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Token expired'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTExpired, self).__init__(msg)


class JWTNotYetValid(JWException):
    """JSON Web Token is not yet valid.

    This exception is raised when a token is not valid yet according to its
    claims.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Token not yet valid'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTNotYetValid, self).__init__(msg)


class JWTMissingClaim(JWException):
    """JSON Web Token claim is invalid.

    This exception is raised when a claim does not match the expected value.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Invalid Claim Value'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTMissingClaim, self).__init__(msg)


class JWTInvalidClaimValue(JWException):
    """JSON Web Token claim is invalid.

    This exception is raised when a claim does not match the expected value.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Invalid Claim Value'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTInvalidClaimValue, self).__init__(msg)


class JWTInvalidClaimFormat(JWException):
    """JSON Web Token claim format is invalid.

    This exception is raised when a claim is not in a valid format.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Invalid Claim Format'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTInvalidClaimFormat, self).__init__(msg)


@deprecated('')
class JWTMissingKeyID(JWException):
    """JSON Web Token is missing key id.

    This exception is raised when trying to decode a JWT with a key set
    that does not have a kid value in its header.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Missing Key ID'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTMissingKeyID, self).__init__(msg)


class JWTMissingKey(JWKeyNotFound):
    """JSON Web Token is using a key not in the key set.

    This exception is raised if the key that was used is not available
    in the passed key set.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = str(message)
        else:
            msg = 'Missing Key'
        if exception:
            msg += ' {%s}' % str(exception)
        super(JWTMissingKey, self).__init__(msg)


class JWT:
    """JSON Web token object

    This object represent a generic token.
    """

    def __init__(self, header=None, claims=None, jwt=None, key=None,
                 algs=None, default_claims=None, check_claims=None,
                 expected_type=None):
        """Creates a JWT object.

        :param header: A dict or a JSON string with the JWT Header data.
        :param claims: A dict or a string with the JWT Claims data.
        :param jwt: a 'raw' JWT token
        :param key: A (:class:`jwcrypto.jwk.JWK`) key to deserialize
         the token. A (:class:`jwcrypto.jwk.JWKSet`) can also be used.
        :param algs: An optional list of allowed algorithms
        :param default_claims: An optional dict with default values for
         registered claims. A None value for NumericDate type claims
         will cause generation according to system time. Only the values
         from RFC 7519 - 4.1 are evaluated.
        :param check_claims: An optional dict of claims that must be
         present in the token, if the value is not None the claim must
         match exactly.
        :param expected_type: An optional string that defines what kind
         of token to expect when validating a deserialized token.
         Supported values: "JWS" or "JWE"
         If left to None the code will try to detect what the expected
         type is based on other parameters like 'algs' and will default
         to JWS if no hints are found. It has no effect on token creation.

        Note: either the header,claims or jwt,key parameters should be
        provided as a deserialization operation (which occurs if the jwt
        is provided) will wipe any header or claim provided by setting
        those obtained from the deserialization of the jwt token.

        Note: if check_claims is not provided the 'exp' and 'nbf' claims
        are checked if they are set on the token but not enforced if not
        set. Any other RFC 7519 registered claims are checked only for
        format conformance.
        """

        self._header = None
        self._claims = None
        self._token = None
        self._algs = algs
        self._reg_claims = None
        self._check_claims = None
        self._leeway = 60  # 1 minute clock skew allowed
        self._validity = 600  # 10 minutes validity (up to 11 with leeway)
        self.deserializelog = None
        self._expected_type = expected_type

        if header:
            self.header = header

        if default_claims is not None:
            self._reg_claims = default_claims

        if check_claims is not None:
            if check_claims is not False:
                self._check_check_claims(check_claims)
            self._check_claims = check_claims

        if claims is not None:
            self.claims = claims

        if jwt is not None:
            self.deserialize(jwt, key)

    @property
    def header(self):
        if self._header is None:
            raise KeyError("'header' not set")
        return self._header

    @header.setter
    def header(self, h):
        if isinstance(h, dict):
            eh = json_encode(h)
        else:
            eh = h
            h = json_decode(eh)

        if h.get('b64') is False:
            raise ValueError("b64 header is invalid."
                             "JWTs cannot use unencoded payloads")
        self._header = eh

    @property
    def claims(self):
        if self._claims is None:
            raise KeyError("'claims' not set")
        return self._claims

    @claims.setter
    def claims(self, data):
        if not isinstance(data, dict):
            if not self._reg_claims:
                # no default_claims, can return immediately
                self._claims = data
                return
            data = json_decode(data)
        else:
            # _add_default_claims modifies its argument
            # so we must always copy it.
            data = copy.deepcopy(data)

        self._add_default_claims(data)
        self._claims = json_encode(data)

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, t):
        if isinstance(t, JWS) or isinstance(t, JWE) or isinstance(t, JWT):
            self._token = t
        else:
            raise TypeError("Invalid token type, must be one of JWS,JWE,JWT")

    @property
    def leeway(self):
        return self._leeway

    @leeway.setter
    def leeway(self, lwy):
        self._leeway = int(lwy)

    @property
    def validity(self):
        return self._validity

    @validity.setter
    def validity(self, v):
        self._validity = int(v)

    def _expected_type_heuristics(self, key=None):
        if self._expected_type is None and self._algs:
            if set(self._algs).issubset(jwe_algs + ['RSA1_5']):
                self._expected_type = "JWE"
            elif set(self._algs).issubset(jws_algs):
                self._expected_type = "JWS"
        if self._expected_type is None and self._header:
            if "enc" in json_decode(self._header):
                self._expected_type = "JWE"
        if self._expected_type is None and key is not None:
            if isinstance(key, JWK):
                use = key.get('use')
                if use == 'sig':
                    self._expected_type = "JWS"
                elif use == 'enc':
                    self._expected_type = "JWE"
            elif isinstance(key, JWKSet):
                all_use = None
                # we can infer only if all keys are of the same type
                for k in key:
                    use = k.get('use')
                    if all_use is None:
                        all_use = use
                    elif use != all_use:
                        all_use = None
                        break
                if all_use == 'sig':
                    self._expected_type = "JWS"
                elif all_use == 'enc':
                    self._expected_type = "JWE"
        if self._expected_type is None and key is not None:
            if isinstance(key, JWK):
                ops = key.get('key_ops')
                if ops:
                    if not isinstance(ops, list):
                        ops = [ops]
                    if set(ops).issubset(['sign', 'verify']):
                        self._expected_type = "JWS"
                    elif set(ops).issubset(['encrypt', 'decrypt']):
                        self._expected_type = "JWE"
            elif isinstance(key, JWKSet):
                all_ops = None
                ttype = None
                # we can infer only if all keys are of the same type
                for k in key:
                    ops = k.get('key_ops')
                    if ops:
                        if not isinstance(ops, list):
                            ops = [ops]
                        if all_ops is None:
                            if set(ops).issubset(['sign', 'verify']):
                                all_ops = set(['sign', 'verify'])
                                ttype = "JWS"
                            elif set(ops).issubset(['encrypt', 'decrypt']):
                                all_ops = set(['encrypt', 'decrypt'])
                                ttype = "JWE"
                            else:
                                ttype = None
                                break
                        else:
                            if not set(ops).issubset(all_ops):
                                ttype = None
                                break
                    elif all_ops:
                        ttype = None
                        break
                if ttype:
                    self._expected_type = ttype
        if self._expected_type is None:
            self._expected_type = "JWS"
        return self._expected_type

    @property
    def expected_type(self):
        if self._expected_type is not None:
            return self._expected_type

        # If no expected type is set we default to accept only JWSs,
        # however to improve backwards compatibility we try some
        # heuristic to see if there has been strong indication of
        # what the expected token type is.
        return self._expected_type_heuristics()

    @expected_type.setter
    def expected_type(self, v):
        if v in ["JWS", "JWE"]:
            self._expected_type = v
        else:
            raise ValueError("Invalid value, must be 'JWS' or 'JWE'")

    def _add_optional_claim(self, name, claims):
        if name in claims:
            return
        val = self._reg_claims.get(name, None)
        if val is not None:
            claims[name] = val

    def _add_time_claim(self, name, claims, defval):
        if name in claims:
            return
        if name in self._reg_claims:
            if self._reg_claims[name] is None:
                claims[name] = defval
            else:
                claims[name] = self._reg_claims[name]

    def _add_jti_claim(self, claims):
        if 'jti' in claims or 'jti' not in self._reg_claims:
            return
        claims['jti'] = str(uuid.uuid4())

    def _add_default_claims(self, claims):
        if self._reg_claims is None:
            return

        now = int(time.time())
        self._add_optional_claim('iss', claims)
        self._add_optional_claim('sub', claims)
        self._add_optional_claim('aud', claims)
        self._add_time_claim('exp', claims, now + self.validity)
        self._add_time_claim('nbf', claims, now)
        self._add_time_claim('iat', claims, now)
        self._add_jti_claim(claims)

    def _check_string_claim(self, name, claims):
        if name not in claims or claims[name] is None:
            return
        if not isinstance(claims[name], str):
            raise JWTInvalidClaimFormat(
                "Claim %s is not a StringOrURI type" % (name, ))

    def _check_array_or_string_claim(self, name, claims):
        if name not in claims or claims[name] is None:
            return
        if isinstance(claims[name], list):
            if any(not isinstance(claim, str) for claim in claims):
                raise JWTInvalidClaimFormat(
                    "Claim %s contains non StringOrURI types" % (name, ))
        elif not isinstance(claims[name], str):
            raise JWTInvalidClaimFormat(
                "Claim %s is not a StringOrURI type" % (name, ))

    def _check_integer_claim(self, name, claims):
        if name not in claims or claims[name] is None:
            return
        try:
            int(claims[name])
        except ValueError as e:
            raise JWTInvalidClaimFormat(
                "Claim %s is not an integer" % (name, )) from e

    def _check_exp(self, claim, limit, leeway):
        if claim < limit - leeway:
            raise JWTExpired('Expired at %d, time: %d(leeway: %d)' % (
                             claim, limit, leeway))

    def _check_nbf(self, claim, limit, leeway):
        if claim > limit + leeway:
            raise JWTNotYetValid('Valid from %d, time: %d(leeway: %d)' % (
                                 claim, limit, leeway))

    def _check_default_claims(self, claims):
        self._check_string_claim('iss', claims)
        self._check_string_claim('sub', claims)
        self._check_array_or_string_claim('aud', claims)
        self._check_integer_claim('exp', claims)
        self._check_integer_claim('nbf', claims)
        self._check_integer_claim('iat', claims)
        self._check_string_claim('jti', claims)
        self._check_string_claim('typ', claims)

        if self._check_claims is None:
            if 'exp' in claims:
                self._check_exp(claims['exp'], time.time(), self._leeway)
            if 'nbf' in claims:
                self._check_nbf(claims['nbf'], time.time(), self._leeway)

    def _check_check_claims(self, check_claims):
        self._check_string_claim('iss', check_claims)
        self._check_string_claim('sub', check_claims)
        self._check_array_or_string_claim('aud', check_claims)
        self._check_integer_claim('exp', check_claims)
        self._check_integer_claim('nbf', check_claims)
        self._check_integer_claim('iat', check_claims)
        self._check_string_claim('jti', check_claims)
        self._check_string_claim('typ', check_claims)

    def _check_provided_claims(self):
        # check_claims can be set to False to skip any check
        if self._check_claims is False:
            return

        try:
            claims = json_decode(self.claims)
            if not isinstance(claims, dict):
                raise ValueError()
        except ValueError as e:
            if self._check_claims is not None:
                raise JWTInvalidClaimFormat("Claims check requested "
                                            "but claims is not a json "
                                            "dict") from e
            return

        self._check_default_claims(claims)

        if self._check_claims is None:
            return

        for name, value in self._check_claims.items():
            if name not in claims:
                raise JWTMissingClaim("Claim %s is missing" % (name, ))

            if name in ['iss', 'sub', 'jti']:
                if value is not None and value != claims[name]:
                    raise JWTInvalidClaimValue(
                        "Invalid '%s' value. Expected '%s' got '%s'" % (
                            name, value, claims[name]))

            elif name == 'aud':
                if value is not None:
                    if isinstance(claims[name], list):
                        tclaims = claims[name]
                    else:
                        tclaims = [claims[name]]
                    if isinstance(value, list):
                        cclaims = value
                    else:
                        cclaims = [value]
                    found = False
                    for v in cclaims:
                        if v in tclaims:
                            found = True
                            break
                    if not found:
                        raise JWTInvalidClaimValue(
                            "Invalid '{}' value. Expected '{}' in '{}'".format(
                                name, claims[name], value))

            elif name == 'exp':
                if value is not None:
                    self._check_exp(claims[name], value, 0)
                else:
                    self._check_exp(claims[name], time.time(), self._leeway)

            elif name == 'nbf':
                if value is not None:
                    self._check_nbf(claims[name], value, 0)
                else:
                    self._check_nbf(claims[name], time.time(), self._leeway)

            elif name == 'typ':
                if value is not None:
                    if self.norm_typ(value) != self.norm_typ(claims[name]):
                        raise JWTInvalidClaimValue("Invalid '%s' value. '%s'"
                                                   " does not normalize to "
                                                   "'%s'" % (name,
                                                             claims[name],
                                                             value))

            else:
                if value is not None and value != claims[name]:
                    raise JWTInvalidClaimValue(
                        "Invalid '%s' value. Expected '%s' got '%s'" % (
                            name, value, claims[name]))

    def norm_typ(self, val):
        lc = val.lower()
        if '/' in lc:
            return lc
        else:
            return 'application/' + lc

    def make_signed_token(self, key):
        """Signs the payload.

        Creates a JWS token with the header as the JWS protected header and
        the claims as the payload. See (:class:`jwcrypto.jws.JWS`) for
        details on the exceptions that may be raised.

        :param key: A (:class:`jwcrypto.jwk.JWK`) key.
        """

        t = JWS(self.claims)
        if self._algs:
            t.allowed_algs = self._algs
        t.add_signature(key, protected=self.header)
        self.token = t
        self._expected_type = "JWS"

    def make_encrypted_token(self, key):
        """Encrypts the payload.

        Creates a JWE token with the header as the JWE protected header and
        the claims as the plaintext. See (:class:`jwcrypto.jwe.JWE`) for
        details on the exceptions that may be raised.

        :param key: A (:class:`jwcrypto.jwk.JWK`) key.
        """

        t = JWE(self.claims, self.header)
        if self._algs:
            t.allowed_algs = self._algs
        t.add_recipient(key)
        self.token = t
        self._expected_type = "JWE"

    def validate(self, key):
        """Validate a JWT token that was deserialized w/o providing a key

        :param key: A (:class:`jwcrypto.jwk.JWK`) verification or
         decryption key, or a (:class:`jwcrypto.jwk.JWKSet`) that
         contains a key indexed by the 'kid' header.
        """
        self.deserializelog = []
        if self.token is None:
            raise ValueError("Token empty")

        et = self._expected_type_heuristics(key)
        validate_fn = None

        if isinstance(self.token, JWS):
            if et != "JWS" and JWT_expect_type:
                raise TypeError("Expected {}, got JWS".format(et))
            validate_fn = self.token.verify
        elif isinstance(self.token, JWE):
            if et != "JWE" and JWT_expect_type:
                raise TypeError("Expected {}, got JWE".format(et))
            validate_fn = self.token.decrypt
        else:
            raise ValueError("Token format unrecognized")

        try:
            validate_fn(key)
            self.deserializelog.append("Success")
        except Exception as e:  # pylint: disable=broad-except
            if isinstance(self.token, JWS):
                self.deserializelog = self.token.verifylog
            elif isinstance(self.token, JWE):
                self.deserializelog = self.token.decryptlog
            self.deserializelog.append(
                'Validation failed: [{}]'.format(repr(e)))
            if isinstance(e, JWKeyNotFound):
                raise JWTMissingKey() from e
            raise

        self.header = self.token.jose_header
        payload = self.token.payload
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        self.claims = payload
        self._check_provided_claims()

    def deserialize(self, jwt, key=None):
        """Deserialize a JWT token.

        NOTE: Destroys any current status and tries to import the raw
        token provided.

        :param jwt: a 'raw' JWT token.
        :param key: A (:class:`jwcrypto.jwk.JWK`) verification or
         decryption key, or a (:class:`jwcrypto.jwk.JWKSet`) that
         contains a key indexed by the 'kid' header.
        """
        data = jwt.count('.')
        if data == 2:
            self.token = JWS()
        elif data == 4:
            self.token = JWE()
        else:
            raise ValueError("Token format unrecognized")

        # Apply algs restrictions if any, before performing any operation
        if self._algs:
            self.token.allowed_algs = self._algs

        self.deserializelog = None
        # now deserialize and also decrypt/verify (or raise) if we
        # have a key
        self.token.deserialize(jwt, None)
        if key:
            self.validate(key)

    def serialize(self, compact=True):
        """Serializes the object into a JWS token.

        :param compact(boolean): must be True.

        Note: the compact parameter is provided for general compatibility
        with the serialize() functions of :class:`jwcrypto.jws.JWS` and
        :class:`jwcrypto.jwe.JWE` so that these objects can all be used
        interchangeably. However the only valid JWT representation is the
        compact representation.

        :return: A json formatted string or a compact representation string
        :rtype: `str`
        """
        if not compact:
            raise ValueError("Only the compact serialization is allowed")

        return self.token.serialize(compact)

    @classmethod
    def from_jose_token(cls, token):
        """Creates a JWT object from a serialized JWT token.

        :param token: A string with the json or compat representation
         of the token.

        :raises InvalidJWEData or InvalidJWSObject: if the raw object is an
         invalid JWT token.

        :return: A JWT token
        :rtype: JWT
        """

        obj = cls()
        obj.deserialize(token)
        return obj

    def __eq__(self, other):
        if not isinstance(other, JWT):
            return False
        return self._claims == other._claims and \
            self._header == other._header and \
            self.token == other.token

    def __str__(self):
        try:
            return self.serialize()
        except Exception:  # pylint: disable=broad-except
            return self.__repr__()

    def __repr__(self):
        jwt = repr(self.token)
        return f'JWT(header={self._header}, ' + \
               f'claims={self._claims}, ' + \
               f'jwt={jwt}, ' + \
               f'key=None, algs={self._algs}, ' + \
               f'default_claims={self._reg_claims}, ' + \
               f'check_claims={self._check_claims})'
