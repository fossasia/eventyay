"""Issue #127 - CATEGORIES comma escaping bug

Tests for categories containing commas.
See https://github.com/collective/icalendar/issues/127
"""

from icalendar import Calendar, Event
from icalendar.prop import vCategory


def test_categories_with_comma_roundtrip():
    """Test that categories containing commas survive round-trip."""
    # Create event with categories containing commas
    event = Event()
    event.add("summary", "Test Event")
    event.add("categories", ["Meeting, John", "Project"])

    # Serialize
    ical_bytes = event.to_ical()
    ical_str = ical_bytes.decode("utf-8")

    # Should contain escaped comma
    assert "Meeting\\, John" in ical_str
    assert "CATEGORIES:Meeting\\, John,Project" in ical_str

    # Parse back
    cal = Calendar.from_ical(ical_bytes)
    parsed_event = cal.walk("VEVENT")[0]
    cats = parsed_event.get("categories")

    # Should have 2 categories, not 3
    cat_list = list(cats) if hasattr(cats, "__iter__") else cats.cats
    assert len(cat_list) == 2
    assert str(cat_list[0]) == "Meeting, John"
    assert str(cat_list[1]) == "Project"


def test_categories_multiple_escaped_commas():
    """Test multiple commas in a single category."""
    event = Event()
    event.add("categories", ["A, B, C", "D"])

    ical_bytes = event.to_ical()

    # Parse back
    cal = Calendar.from_ical(ical_bytes)
    parsed_event = cal.walk("VEVENT")[0]
    cats = parsed_event.get("categories")
    cat_list = list(cats) if hasattr(cats, "__iter__") else cats.cats

    assert len(cat_list) == 2
    assert str(cat_list[0]) == "A, B, C"
    assert str(cat_list[1]) == "D"


def test_categories_no_commas_still_works():
    """Ensure simple categories without commas still work."""
    event = Event()
    event.add("categories", ["Work", "Personal", "Urgent"])

    ical_bytes = event.to_ical()

    cal = Calendar.from_ical(ical_bytes)
    parsed_event = cal.walk("VEVENT")[0]
    cats = parsed_event.get("categories")
    cat_list = list(cats) if hasattr(cats, "__iter__") else cats.cats

    assert len(cat_list) == 3
    assert str(cat_list[0]) == "Work"
    assert str(cat_list[1]) == "Personal"
    assert str(cat_list[2]) == "Urgent"


def test_categories_from_ics_file(calendars):
    """Test parsing categories with escaped commas from ICS file."""
    cal = calendars.issue_127_categories_with_commas
    event = cal.walk("VEVENT")[0]
    cats = event.get("categories")
    cat_list = list(cats) if hasattr(cats, "__iter__") else cats.cats

    # Should parse as 3 categories
    assert len(cat_list) == 3
    assert str(cat_list[0]) == "Meeting, John"
    assert str(cat_list[1]) == "Work, Sarah"
    assert str(cat_list[2]) == "Project"


def test_vcategory_direct_usage():
    """Test vCategory class directly."""
    # Create vCategory with commas
    cat = vCategory(["Meeting, John", "Project"])

    # to_ical should escape commas
    ical = cat.to_ical()
    assert ical == b"Meeting\\, John,Project"

    # from_ical with list should work
    parsed = vCategory.from_ical(["Meeting, John", "Project"])
    assert len(parsed) == 2
    assert parsed[0] == "Meeting, John"
    assert parsed[1] == "Project"


def test_categories_edge_cases():
    """Test edge cases."""
    # Empty category
    event = Event()
    event.add("categories", ["", "Work"])
    ical = event.to_ical()
    cal = Calendar.from_ical(ical)
    cats = list(cal.walk("VEVENT")[0].get("categories"))
    assert len(cats) == 2

    # Only commas
    event2 = Event()
    event2.add("categories", [",,,"])
    ical2 = event2.to_ical()
    assert b"\\,\\,\\," in ical2

    # Spaces around commas
    event3 = Event()
    event3.add("categories", ["A , B", "C"])
    ical3 = event3.to_ical()
    cal3 = Calendar.from_ical(ical3)
    cats3 = list(cal3.walk("VEVENT")[0].get("categories"))
    assert str(cats3[0]) == "A , B"


def test_categories_escaped_escape_sequences():
    """Test escaped backslash followed by comma and double escaped comma."""
    # Category with literal "\," (backslash-comma as two chars)
    event = Event()
    event.add("categories", ["\\,", "Work"])
    ical = event.to_ical()

    # Should have escaped backslash AND escaped comma: \\\\,
    assert b"\\\\\\," in ical

    # Round-trip
    cal = Calendar.from_ical(ical)
    cats = list(cal.walk("VEVENT")[0].get("categories"))
    assert len(cats) == 2
    assert str(cats[0]) == "\\,"
    assert str(cats[1]) == "Work"

    # Category with literal "\\," (backslash, backslash, comma)
    event2 = Event()
    event2.add("categories", ["\\\\,", "Personal"])
    ical2 = event2.to_ical()

    # Should have double escaped backslash and escaped comma
    assert b"\\\\\\\\\\," in ical2

    # Round-trip
    cal2 = Calendar.from_ical(ical2)
    cats2 = list(cal2.walk("VEVENT")[0].get("categories"))
    assert len(cats2) == 2
    assert str(cats2[0]) == "\\\\,"
    assert str(cats2[1]) == "Personal"
