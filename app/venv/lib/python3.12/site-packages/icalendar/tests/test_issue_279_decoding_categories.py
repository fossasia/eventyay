"""This tests decoding categories.

See issue https://github.com/collective/icalendar/issues/279.
"""

from icalendar import Event, Todo


def test_decode_categories_empty():
    """We can decode no categories."""
    event = Event()
    categories = event.decoded("categories", [])
    assert categories == []


def test_decode_categories_when_set():
    """We can decode categories when set."""
    todo = Todo()
    todo.categories = ["cat1", "cat2"]
    categories = todo.decoded("categories", [])
    assert categories == ["cat1", "cat2"]
