import unittest

from icalendar.parser_tools import data_encode, from_unicode, to_unicode


class TestParserTools(unittest.TestCase):
    def test_parser_tools_to_unicode(self):
        assert to_unicode(b"spam") == "spam"
        assert to_unicode("spam") == "spam"
        assert to_unicode(b"spam") == "spam"
        assert to_unicode(b"\xc6\xb5") == "Ƶ"
        assert to_unicode(b"\xc6\xb5") == "Ƶ"
        assert to_unicode(b"\xc6\xb5", encoding="ascii") == "Ƶ"
        assert to_unicode(1) == 1
        assert to_unicode(None) is None

    def test_parser_tools_from_unicode(self):
        assert from_unicode("Ƶ", encoding="ascii") == b"\xc6\xb5"

    def test_parser_tools_data_encode(self):
        data1 = {
            "k1": "v1",
            "k2": "v2",
            "k3": "v3",
            "li1": ["it1", "it2", {"k4": "v4", "k5": "v5"}, 123],
        }
        res = {
            b"k3": b"v3",
            b"k2": b"v2",
            b"k1": b"v1",
            b"li1": [b"it1", b"it2", {b"k5": b"v5", b"k4": b"v4"}, 123],
        }
        assert data_encode(data1) == res
