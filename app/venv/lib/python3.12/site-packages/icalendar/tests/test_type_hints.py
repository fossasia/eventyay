from icalendar.caselessdict import CaselessDict, canonsort_items, canonsort_keys


def test_caselessdict_basic_behavior():
    d = CaselessDict()

    # test __setitem__ and key normalization
    d["a"] = 1
    d["B"] = 2

    assert d["A"] == 1
    assert d["b"] == 2
    assert set(d.keys()) == {"A", "B"}

    # test sorted_keys and sorted_items
    class MyDict(CaselessDict):
        canonical_order = ["A"]

    m = MyDict()
    m["b"] = 2
    m["a"] = 1

    assert m.sorted_keys() == ["A", "B"]
    assert [k for k, _ in m.sorted_items()] == ["A", "B"]


def test_canonsort_keys_basic():
    keys = ["C", "A", "B"]
    canonical = ["B", "A"]

    sorted_keys = canonsort_keys(keys, canonical)

    # canonical keys come first, in order
    assert sorted_keys[:2] == ["B", "A"]

    # remaining keys are alphabetical
    assert sorted_keys == ["B", "A", "C"]


def test_canonsort_items_basic():
    d = {"C": 3, "A": 1, "B": 2}
    canonical = ["A"]

    sorted_items = canonsort_items(d, canonical)

    # First item is canonical
    assert sorted_items[0] == ("A", 1)
    # Remaining keys follow alphabetical order
    assert sorted_items == [("A", 1), ("B", 2), ("C", 3)]
