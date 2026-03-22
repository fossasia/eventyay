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


"""UBJSON draft v12 encoder"""

from struct import pack, Struct
from decimal import Decimal
from io import BytesIO
from math import isinf, isnan

from .compat import Mapping, Sequence, INTEGER_TYPES, UNICODE_TYPE, TEXT_TYPES, BYTES_TYPES
from .markers import (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                      TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                      OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)

# Lookup tables for encoding small intergers, pre-initialised larger integer & float packers
__SMALL_INTS_ENCODED = {i: TYPE_INT8 + pack('>b', i) for i in range(-128, 128)}
__SMALL_UINTS_ENCODED = {i: TYPE_UINT8 + pack('>B', i) for i in range(256)}
__PACK_INT16 = Struct('>h').pack
__PACK_INT32 = Struct('>i').pack
__PACK_INT64 = Struct('>q').pack
__PACK_FLOAT32 = Struct('>f').pack
__PACK_FLOAT64 = Struct('>d').pack

# Prefix applicable to specialised byte array container
__BYTES_ARRAY_PREFIX = ARRAY_START + CONTAINER_TYPE + TYPE_UINT8 + CONTAINER_COUNT


class EncoderException(TypeError):
    """Raised when encoding of an object fails."""


def __encode_decimal(fp_write, item):
    if item.is_finite():
        fp_write(TYPE_HIGH_PREC)
        encoded_val = str(item).encode('utf-8')
        __encode_int(fp_write, len(encoded_val))
        fp_write(encoded_val)
    else:
        fp_write(TYPE_NULL)


def __encode_int(fp_write, item):
    if item >= 0:
        if item < 2 ** 8:
            fp_write(__SMALL_UINTS_ENCODED[item])
        elif item < 2 ** 15:
            fp_write(TYPE_INT16)
            fp_write(__PACK_INT16(item))
        elif item < 2 ** 31:
            fp_write(TYPE_INT32)
            fp_write(__PACK_INT32(item))
        elif item < 2 ** 63:
            fp_write(TYPE_INT64)
            fp_write(__PACK_INT64(item))
        else:
            __encode_decimal(fp_write, Decimal(item))
    elif item >= -(2 ** 7):
        fp_write(__SMALL_INTS_ENCODED[item])
    elif item >= -(2 ** 15):
        fp_write(TYPE_INT16)
        fp_write(__PACK_INT16(item))
    elif item >= -(2 ** 31):
        fp_write(TYPE_INT32)
        fp_write(__PACK_INT32(item))
    elif item >= -(2 ** 63):
        fp_write(TYPE_INT64)
        fp_write(__PACK_INT64(item))
    else:
        __encode_decimal(fp_write, Decimal(item))


def __encode_float(fp_write, item):
    if 1.18e-38 <= abs(item) <= 3.4e38 or item == 0:
        fp_write(TYPE_FLOAT32)
        fp_write(__PACK_FLOAT32(item))
    elif 2.23e-308 <= abs(item) < 1.8e308:
        fp_write(TYPE_FLOAT64)
        fp_write(__PACK_FLOAT64(item))
    elif isinf(item) or isnan(item):
        fp_write(TYPE_NULL)
    else:
        __encode_decimal(fp_write, Decimal(item))


def __encode_float64(fp_write, item):
    if 2.23e-308 <= abs(item) < 1.8e308:
        fp_write(TYPE_FLOAT64)
        fp_write(__PACK_FLOAT64(item))
    elif item == 0:
        fp_write(TYPE_FLOAT32)
        fp_write(__PACK_FLOAT32(item))
    elif isinf(item) or isnan(item):
        fp_write(TYPE_NULL)
    else:
        __encode_decimal(fp_write, Decimal(item))


def __encode_string(fp_write, item):
    encoded_val = item.encode('utf-8')
    length = len(encoded_val)
    if length == 1:
        fp_write(TYPE_CHAR)
    else:
        fp_write(TYPE_STRING)
        if length < 2 ** 8:
            fp_write(__SMALL_UINTS_ENCODED[length])
        else:
            __encode_int(fp_write, length)
    fp_write(encoded_val)


def __encode_bytes(fp_write, item):
    fp_write(__BYTES_ARRAY_PREFIX)
    length = len(item)
    if length < 2 ** 8:
        fp_write(__SMALL_UINTS_ENCODED[length])
    else:
        __encode_int(fp_write, length)
    fp_write(item)
    # no ARRAY_END since length was specified


def __encode_value(fp_write, item, seen_containers, container_count, sort_keys, no_float32, default):
    if isinstance(item, UNICODE_TYPE):
        __encode_string(fp_write, item)

    elif item is None:
        fp_write(TYPE_NULL)

    elif item is True:
        fp_write(TYPE_BOOL_TRUE)

    elif item is False:
        fp_write(TYPE_BOOL_FALSE)

    elif isinstance(item, INTEGER_TYPES):
        __encode_int(fp_write, item)

    elif isinstance(item, float):
        if no_float32:
            __encode_float64(fp_write, item)
        else:
            __encode_float(fp_write, item)

    elif isinstance(item, Decimal):
        __encode_decimal(fp_write, item)

    elif isinstance(item, BYTES_TYPES):
        __encode_bytes(fp_write, item)

    # order important since mappings could also be sequences
    elif isinstance(item, Mapping):
        __encode_object(fp_write, item, seen_containers, container_count, sort_keys, no_float32, default)

    elif isinstance(item, Sequence):
        __encode_array(fp_write, item, seen_containers, container_count, sort_keys, no_float32, default)

    elif default is not None:
        __encode_value(fp_write, default(item), seen_containers, container_count, sort_keys, no_float32, default)

    else:
        raise EncoderException('Cannot encode item of type %s' % type(item))


def __encode_array(fp_write, item, seen_containers, container_count, sort_keys, no_float32, default):
    # circular reference check
    container_id = id(item)
    if container_id in seen_containers:
        raise ValueError('Circular reference detected')
    seen_containers[container_id] = item

    fp_write(ARRAY_START)
    if container_count:
        fp_write(CONTAINER_COUNT)
        __encode_int(fp_write, len(item))

    for value in item:
        __encode_value(fp_write, value, seen_containers, container_count, sort_keys, no_float32, default)

    if not container_count:
        fp_write(ARRAY_END)

    del seen_containers[container_id]


def __encode_object(fp_write, item, seen_containers, container_count, sort_keys, no_float32, default):
    # circular reference check
    container_id = id(item)
    if container_id in seen_containers:
        raise ValueError('Circular reference detected')
    seen_containers[container_id] = item

    fp_write(OBJECT_START)
    if container_count:
        fp_write(CONTAINER_COUNT)
        __encode_int(fp_write, len(item))

    for key, value in sorted(item.items()) if sort_keys else item.items():
        # allow both str & unicode for Python 2
        if not isinstance(key, TEXT_TYPES):
            raise EncoderException('Mapping keys can only be strings')
        encoded_key = key.encode('utf-8')
        length = len(encoded_key)
        if length < 2 ** 8:
            fp_write(__SMALL_UINTS_ENCODED[length])
        else:
            __encode_int(fp_write, length)
        fp_write(encoded_key)

        __encode_value(fp_write, value, seen_containers, container_count, sort_keys, no_float32, default)

    if not container_count:
        fp_write(OBJECT_END)

    del seen_containers[container_id]


def dump(obj, fp, container_count=False, sort_keys=False, no_float32=True, default=None):
    """Writes the given object as UBJSON to the provided file-like object

    Args:
        obj: The object to encode
        fp: write([size])-able object
        container_count (bool): Specify length for container types (including
                                for empty ones). This can aid decoding speed
                                depending on implementation but requires a bit
                                more space and encoding speed could be reduced
                                if getting length of any of the containers is
                                expensive.
        sort_keys (bool): Sort keys of mappings
        no_float32 (bool): Never use float32 to store float numbers (other than
                           for zero). Disabling this might save space at the
                           loss of precision.
        default (callable): Called for objects which cannot be serialised.
                            Should return a UBJSON-encodable version of the
                            object or raise an EncoderException.

    Raises:
        EncoderException: If an encoding failure occured.

    The following Python types and interfaces (ABCs) are supported (as are any
    subclasses):

    +------------------------------+-----------------------------------+
    | Python                       | UBJSON                            |
    +==============================+===================================+
    | (3) str                      | string                            |
    | (2) unicode                  |                                   |
    +------------------------------+-----------------------------------+
    | None                         | null                              |
    +------------------------------+-----------------------------------+
    | bool                         | true, false                       |
    +------------------------------+-----------------------------------+
    | (3) int                      | uint8, int8, int16, int32, int64, |
    | (2) int, long                | high_precision                    |
    +------------------------------+-----------------------------------+
    | float                        | float32, float64, high_precision  |
    +------------------------------+-----------------------------------+
    | Decimal                      | high_precision                    |
    +------------------------------+-----------------------------------+
    | (3) bytes, bytearray         | array (type, uint8)               |
    | (2) str                      | array (type, uint8)               |
    +------------------------------+-----------------------------------+
    | (3) collections.abc.Mapping  | object                            |
    | (2) collections.Mapping      |                                   |
    +------------------------------+-----------------------------------+
    | (3) collections.abc.Sequence | array                             |
    | (2) collections.Sequence     |                                   |
    +------------------------------+-----------------------------------+

    Notes:
    - Items are resolved in the order of this table, e.g. if the item implements
      both Mapping and Sequence interfaces, it will be encoded as a mapping.
    - None and bool do not use an isinstance check
    - Numbers in brackets denote Python version.
    - Only unicode strings in Python 2 are encoded as strings, i.e. for
      compatibility with e.g. Python 3 one MUST NOT use str in Python 2 (as that
      will be interpreted as a byte array).
    - Mapping keys have to be strings: str for Python3 and unicode or str in
      Python 2.
    - float conversion rules (depending on no_float32 setting):
        float32: 1.18e-38 <= abs(value) <= 3.4e38 or value == 0
        float64: 2.23e-308 <= abs(value) < 1.8e308
        For other values Decimal is used.
    """
    if not callable(fp.write):
        raise TypeError('fp.write not callable')
    fp_write = fp.write

    __encode_value(fp_write, obj, {}, container_count, sort_keys, no_float32, default)


def dumpb(obj, container_count=False, sort_keys=False, no_float32=True, default=None):
    """Returns the given object as UBJSON in a bytes instance. See dump() for
       available arguments."""
    with BytesIO() as fp:
        dump(obj, fp, container_count=container_count, sort_keys=sort_keys, no_float32=no_float32, default=default)
        return fp.getvalue()
