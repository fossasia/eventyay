"""
Copyright (c) 2014 Congressus, The Netherlands
Copyright (c) 2017-2023 Raphael Michel and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import datetime
import hashlib
import random
import re
import time

try:
    random = random.SystemRandom()
    using_sysrandom = True
except NotImplementedError:
    import warnings
    warnings.warn('A secure pseudo-random number generator is not available '
                  'on your system. Falling back to Mersenne Twister.')
    using_sysrandom = False


def get_rand_string(length=12, allowed_chars='0123456789abcdef'):
    """
    Returns a securely generated random string. Taken from the Django project

    The default length of 12 with the a-z, A-Z, 0-9 character set returns
    a 71-bit value. log_2((26+26+10)^12) =~ 71 bits
    """
    if not using_sysrandom:
        # This is ugly, and a hack, but it makes things better than
        # the alternative of predictability. This re-seeds the PRNG
        # using a value that is hard for an attacker to predict, every
        # time a random string is required. This may change the
        # properties of the chosen random sequence slightly, but this
        # is better than absolute predictability.
        random.seed(
            hashlib.sha256(
                ("%s%s" % (
                    random.getstate(),
                    time.time())).encode('utf-8')
            ).digest())
    return ''.join([random.choice(allowed_chars) for i in range(length)])


def make_msg_id():
    """
    Create a semi random message id, by using 12 char random hex string and
    a timestamp.
    @return: string consisting of timestamp, -, random value
    """
    random_string = get_rand_string(12)
    timestamp = datetime.datetime.now().strftime("%Y%m%d%I%M%S")
    msg_id = timestamp + "-" + random_string
    return msg_id


def make_id(name):
    """
    Create a random id combined with the creditor name.
    @return string consisting of name (truncated at 22 chars), -,
    12 char rand hex string.
    """
    name = re.sub(r'[^a-zA-Z0-9]', '', name)
    r = get_rand_string(12)
    if len(name) > 22:
        name = name[:22]
    return name + "-" + r


def int_to_decimal_str(integer):
    """
    Helper to convert integers (representing cents) into decimal currency
    string. WARNING: DO NOT TRY TO DO THIS BY DIVISION, FLOATING POINT
    ERRORS ARE NO FUN IN FINANCIAL SYSTEMS.
    @param integer The amount in cents
    @return string The amount in currency with full stop decimal separator
    """
    int_string = str(integer)
    if len(int_string) <= 2:
        return "0." + int_string.zfill(2)
    else:
        return int_string[:-2] + "." + int_string[-2:]


def decimal_str_to_int(decimal_string):
    """
    Helper to decimal currency string into integers (cents).
    WARNING: DO NOT TRY TO DO THIS BY CONVERSION AND MULTIPLICATION,
    FLOATING POINT ERRORS ARE NO FUN IN FINANCIAL SYSTEMS.
    @param string The amount in currency with full stop decimal separator
    @return integer The amount in cents
    """
    int_string = decimal_string.replace('.', '')
    int_string = int_string.lstrip('0')
    return int(int_string)


ADDRESS_MAPPING = (
    ("address_type", "AdrTp"),
    ("department", "Dept"),
    ("subdepartment", "SubDept"),
    ("street_name", "StrtNm"),
    ("building_number", "BldgNb"),
    ("postcode", "PstCd"),
    ("town", "TwnNm"),
    ("country_subdivision", "CtrySubDvsn"),
    ("country", "Ctry"),
)
