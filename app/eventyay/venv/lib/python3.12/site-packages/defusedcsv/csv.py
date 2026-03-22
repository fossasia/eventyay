import re
from csv import (
    QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC, Dialect,
    DictReader, DictWriter as _BaseDictWriter, Error, Sniffer, __doc__, excel,
    excel_tab, field_size_limit, get_dialect, list_dialects, reader,
    register_dialect, unix_dialect, unregister_dialect, writer as _basewriter,
)
from numbers import Number

from . import version as __version__

try:
    # Requires Python >= 3.12
    from csv import QUOTE_NOTNULL, QUOTE_STRINGS  # noqa: F401
    _py312_constants = ["QUOTE_NOTNULL", "QUOTE_STRINGS"]
except ImportError:
    _py312_constants = []


__all__ = ["QUOTE_MINIMAL", "QUOTE_ALL", "QUOTE_NONNUMERIC", "QUOTE_NONE",
           *_py312_constants, "Error", "Dialect", "__doc__", "excel", "excel_tab",
           "field_size_limit", "reader", "writer",
           "register_dialect", "get_dialect", "list_dialects", "Sniffer",
           "unregister_dialect", "__version__", "DictReader", "DictWriter",
           "unix_dialect"]


def _escape(payload):
    if payload is None:
        return payload
    if isinstance(payload, Number):
        return payload

    payload = str(payload)
    if payload and payload[0] in ('@', '+', '-', '=', '|', '%') and not re.match("^-?[0-9,\\.]+$", payload):
        payload = payload.replace("|", "\\|")
        payload = "'" + payload
    return payload


class _ProxyWriter:
    def __init__(self, writer):
        self.writer = writer

    def writerow(self, row):
        try:
            iter(row)
        except TypeError as err:
            msg = "iterable expected, not %s" % type(row).__name__
            raise Error(msg) from err
        return self.writer.writerow(_escape(field) for field in row)

    def writerows(self, rows):
        return self.writer.writerows((_escape(field) for field in row) for row in rows)

    def __getattr__(self, item):
        return getattr(self.writer, item)


def writer(csvfile, dialect='excel', **fmtparams):
    return _ProxyWriter(_basewriter(csvfile, dialect, **fmtparams))


class DictWriter(_BaseDictWriter):
    def __init__(self, f, fieldnames, restval="", extrasaction="raise",
                 dialect="excel", *args, **kwds):
        super().__init__(f, fieldnames, restval, extrasaction, dialect, *args, **kwds)
        self.writer = writer(f, dialect, **kwds)
