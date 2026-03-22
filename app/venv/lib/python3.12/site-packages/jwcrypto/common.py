# Copyright (C) 2015 JWCrypto Project Contributors - see LICENSE file

import copy
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import namedtuple
from collections.abc import MutableMapping

# Padding stripping versions as described in
# RFC 7515 Appendix C


def base64url_encode(payload):
    if not isinstance(payload, bytes):
        payload = payload.encode('utf-8')
    encode = urlsafe_b64encode(payload)
    return encode.decode('utf-8').rstrip('=')


def base64url_decode(payload):
    size = len(payload) % 4
    if size == 2:
        payload += '=='
    elif size == 3:
        payload += '='
    elif size != 0:
        raise ValueError('Invalid base64 string')
    return urlsafe_b64decode(payload.encode('utf-8'))


# JSON encoding/decoding helpers with good defaults

def json_encode(string):
    if isinstance(string, bytes):
        string = string.decode('utf-8')
    return json.dumps(string, separators=(',', ':'), sort_keys=True)


def json_decode(string):
    if isinstance(string, bytes):
        string = string.decode('utf-8')
    return json.loads(string)


class JWException(Exception):
    pass


class InvalidJWAAlgorithm(JWException):
    def __init__(self, message=None):
        msg = 'Invalid JWA Algorithm name'
        if message:
            msg += ' (%s)' % message
        super(InvalidJWAAlgorithm, self).__init__(msg)


class InvalidCEKeyLength(JWException):
    """Invalid CEK Key Length.

    This exception is raised when a Content Encryption Key does not match
    the required length.
    """

    def __init__(self, expected, obtained):
        msg = 'Expected key of length %d bits, got %d' % (expected, obtained)
        super(InvalidCEKeyLength, self).__init__(msg)


class InvalidJWEOperation(JWException):
    """Invalid JWS Object.

    This exception is raised when a requested operation cannot
    be execute due to unsatisfied conditions.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = message
        else:
            msg = 'Unknown Operation Failure'
        if exception:
            msg += ' {%s}' % repr(exception)
        super(InvalidJWEOperation, self).__init__(msg)


class InvalidJWEKeyType(JWException):
    """Invalid JWE Key Type.

    This exception is raised when the provided JWK Key does not match
    the type required by the specified algorithm.
    """

    def __init__(self, expected, obtained):
        msg = 'Expected key type %s, got %s' % (expected, obtained)
        super(InvalidJWEKeyType, self).__init__(msg)


class InvalidJWEKeyLength(JWException):
    """Invalid JWE Key Length.

    This exception is raised when the provided JWK Key does not match
    the length required by the specified algorithm.
    """

    def __init__(self, expected, obtained):
        msg = 'Expected key of length %d, got %d' % (expected, obtained)
        super(InvalidJWEKeyLength, self).__init__(msg)


class InvalidJWSERegOperation(JWException):
    """Invalid JWSE Header Registry Operation.

    This exception is raised when there is an error in trying to add a JW
    Signature or Encryption header to the Registry.
    """

    def __init__(self, message=None, exception=None):
        msg = None
        if message:
            msg = message
        else:
            msg = 'Unknown Operation Failure'
        if exception:
            msg += ' {%s}' % repr(exception)
        super(InvalidJWSERegOperation, self).__init__(msg)


class JWKeyNotFound(JWException):
    """The key needed to complete the operation was not found.

    This exception is raised when a JWKSet is used to perform
    some operation and the key required to successfully complete
    the operation is not found.
    """

    def __init__(self, message=None):
        if message:
            msg = message
        else:
            msg = 'Key Not Found'
        super(JWKeyNotFound, self).__init__(msg)


# JWSE Header Registry definitions

# RFC 7515 - 9.1: JSON Web Signature and Encryption Header Parameters Registry
# HeaderParameters are for both JWS and JWE
JWSEHeaderParameter = namedtuple('Parameter',
                                 'description mustprotect supported check_fn')


class JWSEHeaderRegistry(MutableMapping):
    def __init__(self, init_registry=None):
        if init_registry:
            if isinstance(init_registry, dict):
                self._registry = copy.deepcopy(init_registry)
            else:
                raise InvalidJWSERegOperation('Unknown input type')
        else:
            self._registry = {}

        MutableMapping.__init__(self)

    def check_header(self, h, value):
        if h not in self._registry:
            raise InvalidJWSERegOperation('No header "%s" found in registry'
                                          % h)

        param = self._registry[h]
        if param.check_fn is None:
            return True
        else:
            return param.check_fn(value)

    def __getitem__(self, key):
        return self._registry.__getitem__(key)

    def __iter__(self):
        return self._registry.__iter__()

    def __delitem__(self, key):
        if self._registry[key].mustprotect or \
           self._registry[key].supported:
            raise InvalidJWSERegOperation('Unable to delete protected or '
                                          'supported field')
        else:
            self._registry.__delitem__(key)

    def __setitem__(self, h, jwse_header_param):
        # Check if a header is not supported
        if h in self._registry:
            p = self._registry[h]
            if p.supported:
                raise InvalidJWSERegOperation('Supported header already exists'
                                              ' in registry')
            elif p.mustprotect and not jwse_header_param.mustprotect:
                raise InvalidJWSERegOperation('Header specified should be'
                                              'a protected header')
            else:
                del self._registry[h]

        self._registry[h] = jwse_header_param

    def __len__(self):
        return self._registry.__len__()
