import sys

PY2 = sys.version_info[0] == 2


def _identity(x):  # pragma: no cover
    return x


__all__ = [
    'BytesIO',
    'PY2',
    'StringIO',
    'ascii_lowercase',
    'cmp',
    'configparser',
    'console_to_str',
    'imap',
    'input',
    'integer_types',
    'iteritems',
    'iterkeys',
    'itervalues',
    'izip',
    'number_types',
    'pickle',
    'range_type',
    'reraise',
    'string_types',
    'text_to_native',
    'text_type',
    'unichr',
    'urllib',
    'urlparse',
    'urlparse',
    'urlretrieve',
    '_identity',
]

if PY2:  # pragma: no cover
    unichr = unichr
    text_type = unicode
    string_types = (str, unicode)
    integer_types = (int, long)
    from urllib import urlretrieve

    def text_to_native(s, enc):
        return s.encode(enc)

    def iterkeys(d):
        return d.iterkeys()

    def itervalues(d):
        return d.itervalues()

    def iteritems(d):
        return d.iteritems()

    from cStringIO import StringIO as BytesIO
    from StringIO import StringIO
    import cPickle as pickle
    import ConfigParser as configparser

    from itertools import izip, imap
    range_type = xrange

    cmp = cmp

    input = raw_input
    from string import lower as ascii_lowercase
    import urlparse

    def console_to_str(s):
        return s.decode('utf_8')

    exec('def reraise(tp, value, tb=None):\n raise tp, value, tb')

else:  # pragma: no cover
    unichr = chr
    text_type = str
    string_types = (str, )
    integer_types = (int, )

    def text_to_native(s, enc):
        return s

    def iterkeys(d):
        return iter(d.keys())

    def itervalues(d):
        return iter(d.values())

    def iteritems(d):
        return iter(d.items())

    from io import StringIO
    from io import BytesIO
    import pickle
    import configparser

    izip = zip
    imap = map
    range_type = range

    def cmp(a, b):
        return (a > b) - (a < b)

    input = input
    from string import ascii_lowercase
    import urllib.parse as urllib
    import urllib.parse as urlparse
    from urllib.request import urlretrieve

    if getattr(sys, '__stdout__', None):
        console_encoding = sys.__stdout__.encoding
    else:
        console_encoding = sys.stdout.encoding

    def console_to_str(s):
        ''' From pypa/pip project, pip.backwardwardcompat. License MIT. '''
        try:
            return s.decode(console_encoding)
        except UnicodeDecodeError:
            return s.decode('utf_8')

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise (value.with_traceback(tb))
        raise value


number_types = integer_types + (float, )
