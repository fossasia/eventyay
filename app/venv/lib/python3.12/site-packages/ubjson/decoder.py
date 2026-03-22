# Copyright (c) 2019 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-ubjson/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""UBJSON draft v12 decoder"""

from io import BytesIO
from struct import Struct, pack, error as StructError
from decimal import Decimal, DecimalException

from .compat import raise_from, intern_unicode
from .markers import (TYPE_NONE, TYPE_NULL, TYPE_NOOP, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8,
                      TYPE_INT16, TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR,
                      TYPE_STRING, OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)

__TYPES = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                     TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, ARRAY_START,
                     OBJECT_START))
__TYPES_NO_DATA = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))
__TYPES_INT = frozenset((TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32, TYPE_INT64))

__SMALL_INTS_DECODED = {pack('>b', i): i for i in range(-128, 128)}
__SMALL_UINTS_DECODED = {pack('>B', i): i for i in range(256)}
__UNPACK_INT16 = Struct('>h').unpack
__UNPACK_INT32 = Struct('>i').unpack
__UNPACK_INT64 = Struct('>q').unpack
__UNPACK_FLOAT32 = Struct('>f').unpack
__UNPACK_FLOAT64 = Struct('>d').unpack


class DecoderException(ValueError):
    """Raised when decoding of a UBJSON stream fails."""

    def __init__(self, message, position=None):
        if position is not None:
            super(DecoderException, self).__init__('%s (at byte %d)' % (message, position), position)
        else:
            super(DecoderException, self).__init__(str(message), None)

    @property
    def position(self):
        """Position in stream where decoding failed. Can be None in case where decoding from string of when file-like
        object does not support tell().
        """
        return self.args[1]  # pylint: disable=unsubscriptable-object


# pylint: disable=unused-argument
def __decode_high_prec(fp_read, marker):
    length = __decode_int_non_negative(fp_read, fp_read(1))
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('High prec. too short')
    try:
        return Decimal(raw.decode('utf-8'))
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode decimal string'), ex)
    except DecimalException as ex:
        raise_from(DecoderException('Failed to decode decimal'), ex)


def __decode_int_non_negative(fp_read, marker):
    if marker not in __TYPES_INT:
        raise DecoderException('Integer marker expected')
    value = __METHOD_MAP[marker](fp_read, marker)
    if value < 0:
        raise DecoderException('Negative count/length unexpected')
    return value


def __decode_int8(fp_read, marker):
    try:
        return __SMALL_INTS_DECODED[fp_read(1)]
    except KeyError as ex:
        raise_from(DecoderException('Failed to unpack int8'), ex)


def __decode_uint8(fp_read, marker):
    try:
        return __SMALL_UINTS_DECODED[fp_read(1)]
    except KeyError as ex:
        raise_from(DecoderException('Failed to unpack uint8'), ex)


def __decode_int16(fp_read, marker):
    try:
        return __UNPACK_INT16(fp_read(2))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int16'), ex)


def __decode_int32(fp_read, marker):
    try:
        return __UNPACK_INT32(fp_read(4))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int32'), ex)


def __decode_int64(fp_read, marker):
    try:
        return __UNPACK_INT64(fp_read(8))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int64'), ex)


def __decode_float32(fp_read, marker):
    try:
        return __UNPACK_FLOAT32(fp_read(4))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack float32'), ex)


def __decode_float64(fp_read, marker):
    try:
        return __UNPACK_FLOAT64(fp_read(8))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack float64'), ex)


def __decode_char(fp_read, marker):
    raw = fp_read(1)
    if not raw:
        raise DecoderException('Char missing')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode char'), ex)


def __decode_string(fp_read, marker):
    # current marker is string identifier, so read next byte which identifies integer type
    length = __decode_int_non_negative(fp_read, fp_read(1))
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode string'), ex)


# same as string, except there is no 'S' marker
def __decode_object_key(fp_read, marker, intern_object_keys):
    length = __decode_int_non_negative(fp_read, marker)
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return intern_unicode(raw.decode('utf-8')) if intern_object_keys else raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode object key'), ex)


__METHOD_MAP = {TYPE_NULL: (lambda _, __: None),
                TYPE_BOOL_TRUE: (lambda _, __: True),
                TYPE_BOOL_FALSE: (lambda _, __: False),
                TYPE_INT8: __decode_int8,
                TYPE_UINT8: __decode_uint8,
                TYPE_INT16: __decode_int16,
                TYPE_INT32: __decode_int32,
                TYPE_INT64: __decode_int64,
                TYPE_FLOAT32: __decode_float32,
                TYPE_FLOAT64: __decode_float64,
                TYPE_HIGH_PREC: __decode_high_prec,
                TYPE_CHAR: __decode_char,
                TYPE_STRING: __decode_string}


def __get_container_params(fp_read, in_mapping, no_bytes):
    marker = fp_read(1)
    if marker == CONTAINER_TYPE:
        marker = fp_read(1)
        if marker not in __TYPES:
            raise DecoderException('Invalid container type')
        type_ = marker
        marker = fp_read(1)
    else:
        type_ = TYPE_NONE
    if marker == CONTAINER_COUNT:
        count = __decode_int_non_negative(fp_read, fp_read(1))
        counting = True

        # special cases (no data (None or bool) / bytes array) will be handled in calling functions
        if not (type_ in __TYPES_NO_DATA or
                (type_ == TYPE_UINT8 and not in_mapping and not no_bytes)):
            # Reading ahead is just to capture type, which will not exist if type is fixed
            marker = fp_read(1) if (in_mapping or type_ == TYPE_NONE) else type_

    elif type_ == TYPE_NONE:
        # set to one to indicate that not finished yet
        count = 1
        counting = False
    else:
        raise DecoderException('Container type without count')
    return marker, counting, count, type_


def __decode_object(fp_read, no_bytes, object_hook, object_pairs_hook,  # pylint: disable=too-many-branches
                    intern_object_keys):
    marker, counting, count, type_ = __get_container_params(fp_read, True, no_bytes)
    has_pairs_hook = object_pairs_hook is not None
    obj = [] if has_pairs_hook else {}

    # special case - no data (None or bool)
    if type_ in __TYPES_NO_DATA:
        value = __METHOD_MAP[type_](fp_read, type_)
        if has_pairs_hook:
            for _ in range(count):
                obj.append((__decode_object_key(fp_read, fp_read(1), intern_object_keys), value))
            return object_pairs_hook(obj)

        for _ in range(count):
            obj[__decode_object_key(fp_read, fp_read(1), intern_object_keys)] = value
        return object_hook(obj)

    while count > 0 and (counting or marker != OBJECT_END):
        if marker == TYPE_NOOP:
            marker = fp_read(1)
            continue

        # decode key for object
        key = __decode_object_key(fp_read, marker, intern_object_keys)
        marker = fp_read(1) if type_ == TYPE_NONE else type_

        # decode value
        try:
            value = __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            handled = False
        else:
            handled = True

        # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
        if not handled:
            if marker == ARRAY_START:
                value = __decode_array(fp_read, no_bytes, object_hook, object_pairs_hook, intern_object_keys)
            elif marker == OBJECT_START:
                value = __decode_object(fp_read, no_bytes, object_hook, object_pairs_hook, intern_object_keys)
            else:
                raise DecoderException('Invalid marker within object')

        if has_pairs_hook:
            obj.append((key, value))
        else:
            obj[key] = value
        if counting:
            count -= 1
        if count > 0:
            marker = fp_read(1)

    return object_pairs_hook(obj) if has_pairs_hook else object_hook(obj)


def __decode_array(fp_read, no_bytes, object_hook, object_pairs_hook, intern_object_keys):
    marker, counting, count, type_ = __get_container_params(fp_read, False, no_bytes)

    # special case - no data (None or bool)
    if type_ in __TYPES_NO_DATA:
        return [__METHOD_MAP[type_](fp_read, type_)] * count

    # special case - bytes array
    if type_ == TYPE_UINT8 and not no_bytes:
        container = fp_read(count)
        if len(container) < count:
            raise DecoderException('Container bytes array too short')
        return container

    container = []
    while count > 0 and (counting or marker != ARRAY_END):
        if marker == TYPE_NOOP:
            marker = fp_read(1)
            continue

        # decode value
        try:
            value = __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            handled = False
        else:
            handled = True

        # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
        if not handled:
            if marker == ARRAY_START:
                value = __decode_array(fp_read, no_bytes, object_hook, object_pairs_hook, intern_object_keys)
            elif marker == OBJECT_START:
                value = __decode_object(fp_read, no_bytes, object_hook, object_pairs_hook, intern_object_keys)
            else:
                raise DecoderException('Invalid marker within array')

        container.append(value)
        if counting:
            count -= 1
        if count and type_ == TYPE_NONE:
            marker = fp_read(1)

    return container


def __object_hook_noop(obj):
    return obj


def load(fp, no_bytes=False, object_hook=None, object_pairs_hook=None, intern_object_keys=False):
    """Decodes and returns UBJSON from the given file-like object

    Args:
        fp: read([size])-able object
        no_bytes (bool): If set, typed UBJSON arrays (uint8) will not be
                         converted to a bytes instance and instead treated like
                         any other array (i.e. result in a list).
        object_hook (callable): Called with the result of any object literal
                                decoded (instead of dict).
        object_pairs_hook (callable): Called with the result of any object
                                      literal decoded with an ordered list of
                                      pairs (instead of dict). Takes precedence
                                      over object_hook.
        intern_object_keys (bool): If set, object keys are interned which can
                                   provide a memory saving when many repeated
                                   keys are used. NOTE: This is not supported
                                   in Python2 (since interning does not apply
                                   to unicode) and wil be ignored.

    Returns:
        Decoded object

    Raises:
        DecoderException: If an encoding failure occured.

    UBJSON types are mapped to Python types as follows.  Numbers in brackets
    denote Python version.

        +----------------------------------+---------------+
        | UBJSON                           | Python        |
        +==================================+===============+
        | object                           | dict          |
        +----------------------------------+---------------+
        | array                            | list          |
        +----------------------------------+---------------+
        | string                           | (3) str       |
        |                                  | (2) unicode   |
        +----------------------------------+---------------+
        | uint8, int8, int16, int32, int64 | (3) int       |
        |                                  | (2) int, long |
        +----------------------------------+---------------+
        | float32, float64                 | float         |
        +----------------------------------+---------------+
        | high_precision                   | Decimal       |
        +----------------------------------+---------------+
        | array (typed, uint8)             | (3) bytes     |
        |                                  | (2) str       |
        +----------------------------------+---------------+
        | true                             | True          |
        +----------------------------------+---------------+
        | false                            | False         |
        +----------------------------------+---------------+
        | null                             | None          |
        +----------------------------------+---------------+
    """
    if object_pairs_hook is None and object_hook is None:
        object_hook = __object_hook_noop

    if not callable(fp.read):
        raise TypeError('fp.read not callable')
    fp_read = fp.read

    marker = fp_read(1)
    try:
        try:
            return __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            pass
        if marker == ARRAY_START:
            return __decode_array(fp_read, bool(no_bytes), object_hook, object_pairs_hook, intern_object_keys)
        if marker == OBJECT_START:
            return __decode_object(fp_read, bool(no_bytes), object_hook, object_pairs_hook, intern_object_keys)
        raise DecoderException('Invalid marker')
    except DecoderException as ex:
        raise_from(DecoderException(ex.args[0], position=(fp.tell() if hasattr(fp, 'tell') else None)), ex)


def loadb(chars, no_bytes=False, object_hook=None, object_pairs_hook=None, intern_object_keys=False):
    """Decodes and returns UBJSON from the given bytes or bytesarray object. See
       load() for available arguments."""
    with BytesIO(chars) as fp:
        return load(fp, no_bytes=no_bytes, object_hook=object_hook, object_pairs_hook=object_pairs_hook,
                    intern_object_keys=intern_object_keys)
