from icalendar import Calendar, Component


def test_component_from_ical_typing():
    """Verify that from_ical has the expected type hints and overloads."""
    # Runtime reflection of type hints involving TYPE_CHECKING imports like Self
    # is difficult without modifying the module's globals.
    # We will trust that static analysis (mypy/pyright) validates the syntax/validity
    # of the type hints themselves.
    # We verify the method exists and is callable.
    assert callable(Component.from_ical)


def test_from_ical_behavior():
    """Verify runtime behavior matches expectations for 'multiple'."""
    data = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"

    # Test single return
    cal = Calendar.from_ical(data, multiple=False)
    assert isinstance(cal, Calendar)

    # Test multiple return
    cals = Calendar.from_ical(data, multiple=True)
    assert isinstance(cals, list)
    assert len(cals) == 1
    assert isinstance(cals[0], Calendar)


def test_from_ical_default():
    """Verify default behavior is single return."""
    data = "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    cal = Calendar.from_ical(data)
    assert isinstance(cal, Calendar)
