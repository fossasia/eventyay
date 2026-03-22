"""This tests the compatibility with RFC 7529.

CATEGORIES property

See
- https://github.com/collective/icalendar/issues/655
- https://www.rfc-editor.org/rfc/rfc7529.html
"""

import pytest

from icalendar.cal.calendar import Calendar
from icalendar.cal.event import Event
from icalendar.cal.journal import Journal
from icalendar.cal.todo import Todo

CTJE = Calendar | Event | Journal | Todo


@pytest.fixture(params=[Event, Calendar, Todo, Journal])
def component(request):
    """An empty component with possible categories."""
    return request.param()


def test_no_categories_at_creation(component: CTJE):
    """An empty component has no categories."""
    assert "CATEGORIES" not in component
    assert component.categories == []


def test_add_one_category(component: CTJE):
    """Add one category."""
    component.add("categories", "Lecture")
    assert component.categories == ["Lecture"]


def test_add_multiple_categories(component: CTJE):
    """Add categories."""
    component.add("categories", ["Lecture", "Workshop"])
    assert component.categories == ["Lecture", "Workshop"]


def test_set_categories(component: CTJE):
    """Set categories."""
    component.categories = ["Lecture", "Workshop"]
    assert component.categories == ["Lecture", "Workshop"]


def test_modify_list(component: CTJE):
    """Modify the list and it still works."""
    component.categories = categories = ["cat1"]
    categories.append("cat2")
    assert component.categories == ["cat1", "cat2"]


def test_delete_categories(component: CTJE):
    """Delete categories."""
    component.categories = ["Lecture", "Workshop"]
    del component.categories
    assert "CATEGORIES" not in component
    assert component.categories == []


def test_manage_add_append_remove_categories(component: CTJE):
    """Manage multiple categories by merging them, then append
    and remove a category from the resulting set."""
    component.add("categories", ["c1", "c2"])
    component.add("categories", ["c3", "c4"])
    assert component.categories == ["c1", "c2", "c3", "c4"]
    component.categories.append("c5")
    assert component.categories == ["c1", "c2", "c3", "c4", "c5"]
    component.categories.remove("c2")
    assert component.categories == ["c1", "c3", "c4", "c5"]
    assert "c1,c3,c4,c5" in component.to_ical().decode()
