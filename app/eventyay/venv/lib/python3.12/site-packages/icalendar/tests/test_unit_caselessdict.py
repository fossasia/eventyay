import unittest

import icalendar


class TestCaselessdict(unittest.TestCase):
    def test_caselessdict_canonsort_keys(self):
        canonsort_keys = icalendar.caselessdict.canonsort_keys

        keys = ["DTEND", "DTSTAMP", "DTSTART", "UID", "SUMMARY", "LOCATION"]

        out = canonsort_keys(keys)
        assert out == ["DTEND", "DTSTAMP", "DTSTART", "LOCATION", "SUMMARY", "UID"]

        out = canonsort_keys(
            keys,
            (
                "SUMMARY",
                "DTSTART",
                "DTEND",
            ),
        )
        assert out == ["SUMMARY", "DTSTART", "DTEND", "DTSTAMP", "LOCATION", "UID"]

        out = canonsort_keys(
            keys,
            (
                "UID",
                "DTSTART",
                "DTEND",
            ),
        )
        assert out == ["UID", "DTSTART", "DTEND", "DTSTAMP", "LOCATION", "SUMMARY"]

        out = canonsort_keys(keys, ("UID", "DTSTART", "DTEND", "RRULE", "EXDATE"))
        assert out == ["UID", "DTSTART", "DTEND", "DTSTAMP", "LOCATION", "SUMMARY"]

    def test_caselessdict_canonsort_items(self):
        canonsort_items = icalendar.caselessdict.canonsort_items

        d = {
            "i": 7,
            "c": "at",
            "a": 3.5,
            "l": (2, 3),
            "e": [4, 5],
            "n": 13,
            "d": {"x": "y"},
            "r": 1.0,
        }

        out = canonsort_items(d)
        assert out == [
            ("a", 3.5),
            ("c", "at"),
            ("d", {"x": "y"}),
            ("e", [4, 5]),
            ("i", 7),
            ("l", (2, 3)),
            ("n", 13),
            ("r", 1.0),
        ]

        out = canonsort_items(d, ("i", "c", "a"))
        assert out, [
            ("i", 7),
            ("c", "at"),
            ("a", 3.5),
            ("d", {"x": "y"}),
            ("e", [4, 5]),
            ("l", (2, 3)),
            ("n", 13),
            ("r", 1.0),
        ]

    def test_caselessdict_copy(self):
        CaselessDict = icalendar.caselessdict.CaselessDict

        original_dict = CaselessDict(key1="val1", key2="val2")
        copied_dict = original_dict.copy()

        assert original_dict == copied_dict

    def test_CaselessDict(self):
        CaselessDict = icalendar.caselessdict.CaselessDict

        ncd = CaselessDict(key1="val1", key2="val2")
        assert ncd == CaselessDict({"KEY2": "val2", "KEY1": "val1"})

        assert ncd["key1"] == "val1"
        assert ncd["KEY1"] == "val1"

        assert ncd.has_key("key1")

        ncd["KEY3"] = "val3"
        assert ncd["key3"] == "val3"

        assert ncd.setdefault("key3", "FOUND") == "val3"
        assert ncd.setdefault("key4", "NOT FOUND") == "NOT FOUND"
        assert ncd["key4"] == "NOT FOUND"
        assert ncd.get("key1") == "val1"
        assert ncd.get("key3", "NOT FOUND") == "val3"
        assert ncd.get("key4", "NOT FOUND") == "NOT FOUND"
        assert "key4" in ncd

        del ncd["key4"]
        assert "key4" not in ncd

        ncd.update({"key5": "val5", "KEY6": "val6", "KEY5": "val7"})
        assert ncd["key6"] == "val6"

        keys = sorted(ncd.keys())
        assert keys == ["KEY1", "KEY2", "KEY3", "KEY5", "KEY6"]

    def test_eq_with_non_dict_types(self):
        """Test that CaselessDict.__eq__ handles non-dict comparisons correctly."""
        CaselessDict = icalendar.caselessdict.CaselessDict

        d = CaselessDict()
        d["test"] = 1

        # Should return False for non-dict types, not crash
        assert d != "string"
        assert d != 123
        assert d is not None
        assert d != []
        assert d != ()
        assert d != set()

        # Should still work correctly with dicts
        assert d == {"TEST": 1}
        assert d != {"TEST": 2}
        assert d != {"OTHER": 1}

    def test_ne_with_non_dict_types(self):
        """Test that CaselessDict.__ne__ handles non-dict comparisons correctly."""
        CaselessDict = icalendar.caselessdict.CaselessDict

        d = CaselessDict()
        d["test"] = 1

        # Should return True for non-dict types
        assert d != "string"
        assert d != 123
        assert d is not None
        assert d != []

        # Should still work correctly with dicts
        assert d == {"TEST": 1}
        assert d != {"TEST": 2}
