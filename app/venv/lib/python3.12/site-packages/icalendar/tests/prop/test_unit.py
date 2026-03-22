import unittest
from datetime import date, datetime, time, timedelta

from icalendar.parser import Parameters


class TestProp(unittest.TestCase):
    def test_prop_vFloat(self):
        from icalendar.prop import vFloat

        assert vFloat(1.0).to_ical() == b"1.0"
        assert vFloat.from_ical("42") == 42.0
        assert vFloat(42).to_ical() == b"42.0"
        self.assertRaises(ValueError, vFloat.from_ical, "1s3")

    def test_prop_vInt(self):
        from icalendar.prop import vInt

        assert vInt(42).to_ical() == b"42"
        assert vInt.from_ical("13") == 13
        self.assertRaises(ValueError, vInt.from_ical, "1s3")

    def test_prop_vDDDLists(self):
        from icalendar.prop import vDDDLists

        dt_list = vDDDLists.from_ical("19960402T010000Z")
        assert isinstance(dt_list, list)
        assert len(dt_list) == 1
        assert isinstance(dt_list[0], datetime)
        assert str(dt_list[0]) == "1996-04-02 01:00:00+00:00"

        p = "19960402T010000Z,19960403T010000Z,19960404T010000Z"
        dt_list = vDDDLists.from_ical(p)
        assert len(dt_list) == 3
        assert str(dt_list[0]) == "1996-04-02 01:00:00+00:00"
        assert str(dt_list[2]) == "1996-04-04 01:00:00+00:00"

        dt_list = vDDDLists([])
        assert dt_list.to_ical() == b""

        dt_list = vDDDLists([datetime(2000, 1, 1)])
        assert dt_list.to_ical() == b"20000101T000000"

        dt_list = vDDDLists([datetime(2000, 1, 1), datetime(2000, 11, 11)])
        assert dt_list.to_ical() == b"20000101T000000,20001111T000000"

        instance = vDDDLists([])
        assert instance != "value"

    def test_prop_vDate(self):
        from icalendar.prop import vDate

        assert vDate(date(2001, 1, 1)).to_ical() == b"20010101"
        assert vDate(date(1899, 1, 1)).to_ical() == b"18990101"

        assert vDate.from_ical("20010102") == date(2001, 1, 2)

        self.assertRaises(TypeError, vDate, "d")
        self.assertRaises(ValueError, vDate.from_ical, "200102")

    def test_prop_vDuration(self):
        from icalendar.prop import vDuration

        assert vDuration(timedelta(11)).to_ical() == b"P11D"
        assert vDuration(timedelta(-14)).to_ical() == b"-P14D"
        assert vDuration(timedelta(1, 7384)).to_ical() == b"P1DT2H3M4S"
        assert vDuration(timedelta(1, 7380)).to_ical() == b"P1DT2H3M"
        assert vDuration(timedelta(1, 7200)).to_ical() == b"P1DT2H"
        assert vDuration(timedelta(0, 7200)).to_ical() == b"PT2H"
        assert vDuration(timedelta(0, 7384)).to_ical() == b"PT2H3M4S"
        assert vDuration(timedelta(0, 184)).to_ical() == b"PT3M4S"
        assert vDuration(timedelta(0, 22)).to_ical() == b"PT22S"
        assert vDuration(timedelta(0, 3622)).to_ical() == b"PT1H0M22S"
        assert vDuration(timedelta(days=1, hours=5)).to_ical() == b"P1DT5H"
        assert vDuration(timedelta(hours=-5)).to_ical() == b"-PT5H"
        assert vDuration(timedelta(days=-1, hours=-5)).to_ical() == b"-P1DT5H"

        # How does the parsing work?
        assert vDuration.from_ical("PT1H0M22S") == timedelta(0, 3622)

        self.assertRaises(ValueError, vDuration.from_ical, "kox")

        assert vDuration.from_ical("-P14D") == timedelta(-14)

        self.assertRaises(TypeError, vDuration, 11)

        # calling to_ical twice should result in same output
        duration = vDuration(timedelta(days=-1, hours=-5))
        assert duration.to_ical() == b"-P1DT5H"
        assert duration.to_ical() == b"-P1DT5H"

    def test_prop_vWeekday(self):
        from icalendar.prop import vWeekday

        assert vWeekday("mo").to_ical() == b"MO"
        self.assertRaises(ValueError, vWeekday, "erwer")
        assert vWeekday.from_ical("mo") == "MO"
        assert vWeekday.from_ical("+3mo") == "+3MO"
        self.assertRaises(ValueError, vWeekday.from_ical, "Saturday")
        assert vWeekday("+mo").to_ical() == b"+MO"
        assert vWeekday("+3mo").to_ical() == b"+3MO"
        assert vWeekday("-tu").to_ical() == b"-TU"

    def test_prop_vFrequency(self):
        from icalendar.prop import vFrequency

        self.assertRaises(ValueError, vFrequency, "bad test")
        assert vFrequency("daily").to_ical() == b"DAILY"
        assert vFrequency("daily").from_ical("MONTHLY") == "MONTHLY"
        self.assertRaises(ValueError, vFrequency.from_ical, 234)

    def test_prop_vRecur(self):
        from icalendar.prop import vRecur

        # Let's see how close we can get to one from the rfc:
        # FREQ=YEARLY;INTERVAL=2;BYMONTH=1;BYDAY=SU;BYHOUR=8,9;BYMINUTE=30

        r = {"freq": "yearly", "interval": 2}
        r.update({"bymonth": 1, "byday": "su", "byhour": [8, 9], "byminute": 30})
        assert (
            vRecur(r).to_ical()
            == b"FREQ=YEARLY;INTERVAL=2;BYMINUTE=30;BYHOUR=8,9;BYDAY=SU;BYMONTH=1"
        )

        r = vRecur(FREQ="yearly", INTERVAL=2)
        r.update(
            {
                "BYMONTH": 1,
                "BYDAY": "su",
                "BYHOUR": [8, 9],
                "BYMINUTE": 30,
            }
        )
        assert (
            r.to_ical()
            == b"FREQ=YEARLY;INTERVAL=2;BYMINUTE=30;BYHOUR=8,9;BYDAY=SU;BYMONTH=1"
        )

        r = vRecur(freq="DAILY", count=10)
        r["bysecond"] = [0, 15, 30, 45]
        assert r.to_ical() == b"FREQ=DAILY;COUNT=10;BYSECOND=0,15,30,45"

        r = vRecur(freq="DAILY", until=datetime(2005, 1, 1, 12, 0, 0))
        assert r.to_ical() == b"FREQ=DAILY;UNTIL=20050101T120000"

        # How do we fare with regards to parsing?
        r = vRecur.from_ical("FREQ=DAILY;INTERVAL=2;COUNT=10")
        assert r == {"COUNT": [10], "FREQ": ["DAILY"], "INTERVAL": [2]}
        assert vRecur(r).to_ical() == b"FREQ=DAILY;COUNT=10;INTERVAL=2"

        r = vRecur.from_ical(
            "FREQ=YEARLY;INTERVAL=2;BYMONTH=1;BYDAY=-SU;BYHOUR=8,9;BYMINUTE=30"
        )
        assert r == {
            "BYHOUR": [8, 9],
            "BYDAY": ["-SU"],
            "BYMINUTE": [30],
            "BYMONTH": [1],
            "FREQ": ["YEARLY"],
            "INTERVAL": [2],
        }

        assert (
            vRecur(r).to_ical()
            == b"FREQ=YEARLY;INTERVAL=2;BYMINUTE=30;BYHOUR=8,9;BYDAY=-SU;BYMONTH=1"
        )

        r = vRecur.from_ical("FREQ=WEEKLY;INTERVAL=1;BYWEEKDAY=TH")

        assert r == {"FREQ": ["WEEKLY"], "INTERVAL": [1], "BYWEEKDAY": ["TH"]}

        assert vRecur(r).to_ical() == b"FREQ=WEEKLY;INTERVAL=1;BYWEEKDAY=TH"

        # Some examples from the spec
        r = vRecur.from_ical("FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1")
        assert vRecur(r).to_ical() == b"FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1"

        p = "FREQ=YEARLY;INTERVAL=2;BYMONTH=1;BYDAY=SU;BYHOUR=8,9;BYMINUTE=30"
        r = vRecur.from_ical(p)
        assert (
            vRecur(r).to_ical()
            == b"FREQ=YEARLY;INTERVAL=2;BYMINUTE=30;BYHOUR=8,9;BYDAY=SU;BYMONTH=1"
        )

        # and some errors
        self.assertRaises(ValueError, vRecur.from_ical, "BYDAY=12")

        # when key is not RFC-compliant, parse it as vText
        r = vRecur.from_ical("FREQ=MONTHLY;BYOTHER=TEXT;BYEASTER=-3")
        assert vRecur(r).to_ical() == b"FREQ=MONTHLY;BYEASTER=-3;BYOTHER=TEXT"

    def test_prop_vText(self):
        from icalendar.parser import Contentline
        from icalendar.prop import vText

        assert vText("Simple text").to_ical() == b"Simple text"

        # Escaped text
        t = vText("Text ; with escaped, chars")
        assert t.to_ical() == b"Text \\; with escaped\\, chars"

        # Escaped newlines
        assert (
            vText("Text with escaped\\N chars").to_ical()
            == b"Text with escaped\\n chars"
        )

        # If you pass a unicode object, it will be utf-8 encoded. As this is
        # the (only) standard that RFC 5545 support.
        t = vText("international chars \xe4\xf6\xfc")
        assert t.to_ical() == b"international chars \xc3\xa4\xc3\xb6\xc3\xbc"

        # and parsing?
        _, _, value = Contentline("SUMMARY:Text \\; with escaped\\, chars").parts()
        assert vText.from_ical(value) == "Text ; with escaped, chars"

        _, _, value = Contentline(
            "SUMMARY:A string with\\; some\\\\ characters in\\it"
        ).parts()
        assert vText.from_ical(value) == "A string with; some\\ characters in\\it"

        # We are forgiving to utf-8 encoding errors:
        # We intentionally use a string with unexpected encoding
        #
        assert vText.from_ical(b"Ol\xe9") == "Ol�"

        # Notice how accented E character, encoded with latin-1, got replaced
        # with the official U+FFFD REPLACEMENT CHARACTER.

    def test_prop_vTime(self):
        from icalendar.prop import vTime

        assert vTime(12, 30, 0).to_ical() == "123000"
        assert vTime.from_ical("123000") == time(12, 30)

        # We should also fail, right?
        self.assertRaises(ValueError, vTime.from_ical, "263000")

        self.assertRaises(ValueError, vTime, "263000")

    def test_prop_vUri(self):
        from icalendar.prop import vUri

        assert vUri("http://www.example.com/").to_ical() == b"http://www.example.com/"
        assert vUri.from_ical("http://www.example.com/") == "http://www.example.com/"

    def test_prop_vGeo(self):
        from icalendar.prop import vGeo

        # Pass a list
        assert vGeo([1.2, 3.0]).to_ical() == "1.2;3.0"

        # Pass a tuple
        assert vGeo((1.2, 3.0)).to_ical() == "1.2;3.0"

        g = vGeo.from_ical("37.386013;-122.082932")
        assert g == (float("37.386013"), float("-122.082932"))

        assert vGeo(g).to_ical() == "37.386013;-122.082932"

        self.assertRaises(ValueError, vGeo, "g")
        self.assertRaises(ValueError, vGeo.from_ical, "1s3;1s3")

    def test_prop_vUTCOffset(self):
        from icalendar.prop import vUTCOffset

        assert vUTCOffset(timedelta(hours=2)).to_ical() == "+0200"

        assert vUTCOffset(timedelta(hours=-5)).to_ical() == "-0500"

        assert vUTCOffset(timedelta()).to_ical() == "+0000"

        assert vUTCOffset(timedelta(minutes=-30)).to_ical() == "-0030"

        assert vUTCOffset(timedelta(hours=2, minutes=-30)).to_ical() == "+0130"

        assert vUTCOffset(timedelta(hours=1, minutes=30)).to_ical() == "+0130"

        # Support seconds
        assert (
            vUTCOffset(timedelta(hours=1, minutes=30, seconds=7)).to_ical() == "+013007"
        )

        # Parsing

        assert vUTCOffset.from_ical("0000") == timedelta(0)
        assert vUTCOffset.from_ical("-0030") == timedelta(-1, 84600)
        assert vUTCOffset.from_ical("+0200") == timedelta(0, 7200)
        assert vUTCOffset.from_ical("+023040") == timedelta(0, 9040)

        assert vUTCOffset(vUTCOffset.from_ical("+0230")).to_ical() == "+0230"

        # And a few failures
        self.assertRaises(ValueError, vUTCOffset.from_ical, "+323k")

        self.assertRaises(ValueError, vUTCOffset.from_ical, "+2400")

        self.assertRaises(TypeError, vUTCOffset, "0:00:00")

    def test_prop_vInline(self):
        from icalendar.prop import vInline

        assert vInline("Some text") == "Some text"
        assert vInline("Some text").to_ical() == b"Some text"
        assert vInline.from_ical("Some text") == "Some text"

        t2 = vInline("other text")
        t2.params["cn"] = "Test Osterone"
        assert isinstance(t2.params, Parameters)
        assert t2.params == {"CN": "Test Osterone"}

    def test_prop_vCategory(self):
        from icalendar.prop import vCategory

        catz = ["cat 1", "cat 2", "cat 3"]
        v_cat = vCategory(catz)

        assert v_cat.to_ical() == b"cat 1,cat 2,cat 3"
        assert vCategory.from_ical(v_cat.to_ical()) == catz
        c = vCategory(vCategory.from_ical("APPOINTMENT,EDUCATION"))
        cats = list(c)
        assert cats == ["APPOINTMENT", "EDUCATION"]

    def test_prop_TypesFactory(self):
        from icalendar.prop import TypesFactory

        # To get a type you can use it like this.
        factory = TypesFactory()
        datetime_parser = factory["date-time"]
        assert datetime_parser(datetime(2001, 1, 1)).to_ical() == b"20010101T000000"

        # A typical use is when the parser tries to find a content type and use
        # text as the default
        value = "20050101T123000"
        value_type = "date-time"
        assert factory.get(value_type, "text").from_ical(value) == datetime(
            2005, 1, 1, 12, 30
        )

        # It can also be used to directly encode property and parameter values
        assert (
            factory.to_ical("comment", "by Rasmussen, Max Müller")
            == b"by Rasmussen\\, Max M\xc3\xbcller"
        )
        assert factory.to_ical("priority", 1) == b"1"
        assert (
            factory.to_ical("cn", "Rasmussen, Max Müller")
            == b"Rasmussen\\, Max M\xc3\xbcller"
        )
        assert (
            factory.from_ical("cn", b"Rasmussen\\, Max M\xc3\xb8ller")
            == "Rasmussen\\, Max Møller"
        )
