"""The RFC contains examples of conversions that we can use here."""

from icalendar import Event, vGeo


def test_convert_text_property_example():
    """Convert the example from Section 3.4 of :rfc:`7265`."""
    event = Event()
    event.add("SUMMARY", "Meeting with Fred")
    event.add("categories", ["Meetings", "Work"])
    jcal = event.to_jcal()
    assert jcal == [
        "vevent",
        [
            [
                "summary",
                {},
                "text",
                "Meeting with Fred",
            ],
            [
                "categories",
                {},
                "text",
                "Meetings",
                "Work",
            ],
        ],
        [],
    ]


def test_vGeo():
    """Check convertion of vGeo"""
    geo = vGeo((37.386013, -122.082932))
    assert geo.to_jcal("geo") == ["geo", {}, "float", [37.386013, -122.082932]]


def test_request_status(events):
    """Convert the request status example."""
    event: Event = events.rfc_7265_request_status
    jcal = event.to_jcal()
    assert jcal[1][0] == ["request-status", {}, "text", ["2.0", "Success"]], (
        "request-status 1"
    )
    assert jcal[1][1] == [
        "request-status",
        {},
        "text",
        ["3.7", "Invalid calendar user", "ATTENDEE:mailto:jsmith@example.org"],
    ], "request-status 2"
    assert jcal == [
        "vevent",
        [
            ["request-status", {}, "text", ["2.0", "Success"]],
            [
                "request-status",
                {},
                "text",
                ["3.7", "Invalid calendar user", "ATTENDEE:mailto:jsmith@example.org"],
            ],
        ],
        [],
    ], "whole component"
