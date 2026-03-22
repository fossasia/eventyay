import unittest

import pytest

from icalendar.parser import (
    Contentline,
    Contentlines,
    Parameters,
    dquote,
    foldline,
    q_join,
    q_split,
)
from icalendar.prop import vText


class IcalendarTestCase(unittest.TestCase):
    def setUp(self):
        if not hasattr(self, "assertRaisesRegex"):
            self.assertRaisesRegex = self.assertRaisesRegexp

    def test_long_lines(self):
        c = Contentlines([Contentline("BEGIN:VEVENT")])
        c.append(Contentline("".join("123456789 " * 10)))
        assert (
            c.to_ical()
            == b"BEGIN:VEVENT\r\n123456789 123456789 123456789 123456789 "  # noqa: ISC003
            + b"123456789 123456789 123456789 1234\r\n 56789 123456789 "
            + b"123456789 \r\n"
        )

        # from doctests
        # Notice that there is an extra empty string in the end of the content
        # lines. That is so they can be easily joined with:
        # '\r\n'.join(contentlines))
        assert Contentlines.from_ical("A short line\r\n") == ["A short line", ""]
        assert Contentlines.from_ical("A faked\r\n  long line\r\n") == [
            "A faked long line",
            "",
        ]
        assert Contentlines.from_ical(
            "A faked\r\n  long line\r\nAnd another lin\r\n\te that is folded\r\n"
        ) == ["A faked long line", "And another line that is folded", ""]

    def test_contentline_class(self):
        assert (
            Contentline("Si meliora dies, ut vina, poemata reddit").to_ical()
            == b"Si meliora dies, ut vina, poemata reddit"
        )

        # A long line gets folded
        c = Contentline("".join(["123456789 "] * 10)).to_ical()
        assert (
            c
            == b"123456789 123456789 123456789 123456789 123456789 123456789 "  # noqa: ISC003
            + b"123456789 1234\r\n 56789 123456789 123456789 "
        )

        # A folded line gets unfolded
        assert (
            Contentline.from_ical(c)
            == "123456789 123456789 123456789 123456789 123456789 123456789 "  # noqa: ISC003
            + "123456789 123456789 123456789 123456789 "
        )

        # https://tools.ietf.org/html/rfc5545#section-3.3.11
        # An intentional formatted text line break MUST only be included in
        # a "TEXT" property value by representing the line break with the
        # character sequence of BACKSLASH, followed by a LATIN SMALL LETTER
        # N or a LATIN CAPITAL LETTER N, that is "\n" or "\N".

        # Newlines are not allowed in content lines
        self.assertRaises(AssertionError, Contentline, b"1234\r\n\r\n1234")

        assert Contentline("1234\\n\\n1234").to_ical() == b"1234\\n\\n1234"

        # We do not fold within a UTF-8 character
        c = Contentline(
            b"This line has a UTF-8 character where it should be "
            b"folded. Make sure it g\xc3\xabts folded before that "
            b"character."
        )

        assert b"\xc3\xab" in c.to_ical()

        # Another test of the above
        c = Contentline(b"x" * 73 + b"\xc3\xab" + b"\\n " + b"y" * 10)

        assert c.to_ical().count(b"\xc3") == 1

        # Don't fail if we fold a line that is exactly X times 74 characters
        # long
        Contentline("".join(["x"] * 148)).to_ical()

        # It can parse itself into parts,
        # which is a tuple of (name, params, vals)
        assert Contentline("dtstart:20050101T120000").parts() == (
            "dtstart",
            Parameters({}),
            "20050101T120000",
        )

        assert Contentline("dtstart;value=datetime:20050101T120000").parts() == (
            "dtstart",
            Parameters({"VALUE": "datetime"}),
            "20050101T120000",
        )

        c = Contentline(
            "ATTENDEE;CN=Max Rasmussen;ROLE=REQ-PARTICIPANT:MAILTO:maxm@example.com"
        )
        assert c.parts() == (
            "ATTENDEE",
            Parameters({"ROLE": "REQ-PARTICIPANT", "CN": "Max Rasmussen"}),
            "MAILTO:maxm@example.com",
        )
        assert (
            c.to_ical().decode("utf-8")
            == "ATTENDEE;CN=Max Rasmussen;ROLE=REQ-PARTICIPANT:MAILTO:maxm@example.com"
        )

        # and back again
        # NOTE: we are quoting property values with spaces in it.
        parts = (
            "ATTENDEE",
            Parameters({"ROLE": "REQ-PARTICIPANT", "CN": "Max Rasmussen"}),
            "MAILTO:maxm@example.com",
        )
        assert (
            Contentline.from_parts(*parts)
            == 'ATTENDEE;CN="Max Rasmussen";ROLE=REQ-PARTICIPANT:MAILTO:maxm@example.com'
        )

        # and again
        parts = ("ATTENDEE", Parameters(), "MAILTO:maxm@example.com")
        assert Contentline.from_parts(*parts) == "ATTENDEE:MAILTO:maxm@example.com"

        # A value can also be any of the types defined in PropertyValues
        parts = ("ATTENDEE", Parameters(), vText("MAILTO:test@example.com"))
        assert Contentline.from_parts(*parts) == "ATTENDEE:MAILTO:test@example.com"

        # A value in UTF-8
        parts = ("SUMMARY", Parameters(), vText("INternational char æ ø å"))
        assert Contentline.from_parts(*parts) == "SUMMARY:INternational char æ ø å"

        # A value can also be unicode
        parts = ("SUMMARY", Parameters(), vText("INternational char æ ø å"))
        assert Contentline.from_parts(*parts) == "SUMMARY:INternational char æ ø å"

        # Traversing could look like this.
        name, params, vals = c.parts()
        assert name == "ATTENDEE"
        assert vals == "MAILTO:maxm@example.com"
        assert sorted(params.items()) == sorted(
            [("ROLE", "REQ-PARTICIPANT"), ("CN", "Max Rasmussen")]
        )

        # And the traditional failure
        with pytest.raises(
            ValueError, match="Content line could not be parsed into parts"
        ):
            Contentline("ATTENDEE;maxm@example.com").parts()

        # Another failure:
        with pytest.raises(
            ValueError, match="Content line could not be parsed into parts"
        ):
            Contentline(":maxm@example.com").parts()

        assert Contentline("key;param=:value").parts() == (
            "key",
            Parameters({"PARAM": ""}),
            "value",
        )

        assert Contentline('key;param="pvalue":value').parts() == (
            "key",
            Parameters({"PARAM": "pvalue"}),
            "value",
        )

        # Should bomb on missing param:
        with pytest.raises(
            ValueError, match="Content line could not be parsed into parts"
        ):
            Contentline.from_ical("k;:no param").parts()

        assert Contentline("key;param=pvalue:value", strict=False).parts() == (
            "key",
            Parameters({"PARAM": "pvalue"}),
            "value",
        )

        # If strict is set to True, uppercase param values that are not
        # double-quoted, this is because the spec says non-quoted params are
        # case-insensitive.
        assert Contentline("key;param=pvalue:value", strict=True).parts() == (
            "key",
            Parameters({"PARAM": "PVALUE"}),
            "value",
        )

        assert Contentline('key;param="pValue":value', strict=True).parts() == (
            "key",
            Parameters({"PARAM": "pValue"}),
            "value",
        )

        contains_base64 = (
            b"X-APPLE-STRUCTURED-LOCATION;"
            b'VALUE=URI;X-ADDRESS="Kaiserliche Hofburg, 1010 Wien";'
            b"X-APPLE-MAPKIT-HANDLE=CAESxQEZgr3QZXJyZWljaA==;"
            b"X-APPLE-RADIUS=328.7978217977285;X-APPLE-REFERENCEFRAME=1;"
            b"X-TITLE=Heldenplatz:geo:48.206686,16.363235"
        )

        assert Contentline(contains_base64, strict=True).parts() == (
            "X-APPLE-STRUCTURED-LOCATION",
            Parameters(
                {
                    "X-APPLE-RADIUS": "328.7978217977285",
                    "X-ADDRESS": "Kaiserliche Hofburg, 1010 Wien",
                    "X-APPLE-REFERENCEFRAME": "1",
                    "X-TITLE": "HELDENPLATZ",
                    "X-APPLE-MAPKIT-HANDLE": "CAESXQEZGR3QZXJYZWLJAA==",
                    "VALUE": "URI",
                }
            ),
            "geo:48.206686,16.363235",
        )

    def test_fold_line(self):
        assert foldline("foo") == "foo"
        assert (
            foldline(
                "Lorem ipsum dolor sit amet, consectetur adipiscing "
                "elit. Vestibulum convallis imperdiet dui posuere.",
            )
            == "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Vestibulum conval\r\n lis imperdiet dui posuere."
        )

        # I don't really get this test
        # at least just but bytes in there
        # porting it to "run" under python 2 & 3 makes it not much better
        with pytest.raises(AssertionError):
            foldline("привет".encode(), limit=3)

        assert foldline("foobar", limit=4) == "foo\r\n bar"
        assert (
            foldline(
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit"
                ". Vestibulum convallis imperdiet dui posuere.",
            )
            == "Lorem ipsum dolor sit amet, consectetur adipiscing elit."  # noqa: ISC003
            + " Vestibulum conval\r\n lis imperdiet dui posuere."
        )
        assert (
            foldline("DESCRIPTION:АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЬЫЪЭЮЯ")
            == "DESCRIPTION:АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЬЫЪЭ\r\n ЮЯ"
        )

    def test_value_double_quoting(self):
        assert dquote("Max") == "Max"
        assert dquote("Rasmussen, Max") == '"Rasmussen, Max"'
        assert dquote("name:value") == '"name:value"'

    def test_q_split(self):
        assert q_split('Max,Moller,"Rasmussen, Max"') == [
            "Max",
            "Moller",
            '"Rasmussen, Max"',
        ]

    def test_q_split_bin(self):
        for s in ("X-SOMETHING=ABCDE==", ",,,"):
            for maxsplit in range(-1, 3):
                assert q_split(s, "=", maxsplit=maxsplit) == s.split("=", maxsplit)

    def test_q_join(self):
        assert (
            q_join(["Max", "Moller", "Rasmussen, Max"]) == 'Max,Moller,"Rasmussen, Max"'
        )
