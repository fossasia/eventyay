"""Test code for categories."""

import pytest

from icalendar.prop import vCategory, vText


# we also work on text
@pytest.fixture(params=[vCategory, vText])
def v_cat(request):
    """Fixture for vCategory and vText."""
    return request.param


def test_categories_parse_with_no_items(v_cat):
    """We make sure all items are collected."""
    cats = v_cat.from_jcal(["categories", {}, "text", ""])
    assert cats.cats == [""]


def test_categories_parse_with_more_items(v_cat):
    """We make sure all items are collected."""
    cats = v_cat.from_jcal(["categories", {}, "text", "WORK", "PERSONAL", "URGENT"])
    assert cats.cats == ["WORK", "PERSONAL", "URGENT"]


def test_category_jcal_with_1_item():
    """Check converting vCategory to and from jCal."""
    cats = vCategory(["item 1"])
    jcal = cats.to_jcal("CATEGORIES")
    assert jcal == ["CATEGORIES", {}, "text", "item 1"]


def test_category_jcal_with_0_items():
    """Check converting vCategory to and from jCal."""
    cats = vCategory([])
    jcal = cats.to_jcal("CATEGORIES")
    assert jcal == ["CATEGORIES", {}, "text", ""]


def test_category_jcal_with_1_empty_item():
    """Check converting vCategory to and from jCal."""
    cats = vCategory([""])
    jcal = cats.to_jcal("CATEGORIES")
    assert jcal == ["CATEGORIES", {}, "text", ""]


def test_category_jcal_with_3_items():
    """Check converting vCategory to and from jCal."""
    cats = vCategory(["item 1", "item 2", "item 3"])
    jcal = cats.to_jcal("CATEGORIES")
    assert jcal == ["CATEGORIES", {}, "text", "item 1", "item 2", "item 3"]
