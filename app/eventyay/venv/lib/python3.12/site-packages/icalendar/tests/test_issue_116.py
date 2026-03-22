import icalendar.cal.event


def test_issue_116():
    """Issue #116/#117 - How to add 'X-APPLE-STRUCTURED-LOCATION'
    https://github.com/collective/icalendar/issues/116
    https://github.com/collective/icalendar/issues/117
    """
    event = icalendar.cal.event.Event()
    event.add(
        "X-APPLE-STRUCTURED-LOCATION",
        "geo:-33.868900,151.207000",
        parameters={
            "VALUE": "URI",
            "X-ADDRESS": "367 George Street Sydney CBD NSW 2000",
            "X-APPLE-RADIUS": "72",
            "X-TITLE": "367 George Street",
        },
    )
    assert event.to_ical() == (
        b"BEGIN:VEVENT\r\nX-APPLE-STRUCTURED-LOCATION;VALUE=URI;"
        b'X-ADDRESS="367 George Street Sydney \r\n CBD NSW 2000";'
        b'X-APPLE-RADIUS=72;X-TITLE="367 George Street":'
        b"geo:-33.868900\r\n \\,151.207000\r\nEND:VEVENT\r\n"
    )

    # roundtrip
    assert (
        event.to_ical()
        == icalendar.cal.event.Event.from_ical(event.to_ical()).to_ical()
    )
