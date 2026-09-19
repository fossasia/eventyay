import datetime as dt
import json
from io import BytesIO

import pandas
import pytest

from eventyay.storage.schedule_to_json import convert


def make_schedule_xlsx():
    """Build a minimal in-memory schedule import sheet (Rooms/Tracks/Speakers/Talks)."""
    buffer = BytesIO()
    with pandas.ExcelWriter(buffer, engine="openpyxl") as writer:
        pandas.DataFrame({"ID": [1], "Name": ["Main Room"], "GUID": [""]}).to_excel(
            writer, sheet_name="Rooms", index=False
        )
        pandas.DataFrame({"ID": [1], "Name": ["Default"], "Colour": ["#ff0000"]}).to_excel(
            writer, sheet_name="Tracks", index=False
        )
        pandas.DataFrame(
            {"ID": [1], "Name": ["Jane Doe"], "Avatar": [""], "Biography": [""]}
        ).to_excel(writer, sheet_name="Speakers", index=False)
        pandas.DataFrame(
            {
                "ID": [1],
                "Title": ["Opening"],
                "Abstract": ["Welcome"],
                "Speaker IDs": ["1"],
                "Track ID": [1],
                "Start": [dt.datetime(2026, 10, 1, 9, 0)],
                "End": [dt.datetime(2026, 10, 1, 9, 30)],
                "Room ID": [1],
                "Description": [""],
                "URL": [""],
            }
        ).to_excel(writer, sheet_name="Talks", index=False)
    buffer.seek(0)
    return buffer


@pytest.mark.parametrize("timezone", [None, "Europe/Berlin"])
def test_convert_version_is_timezone_aware(timezone):
    """The top-level "version" must be a timezone-aware ISO timestamp.

    Regression test: previously ``dt.datetime.now()`` produced a naive,
    server-local timestamp while talk times used the event timezone.
    """
    result = json.loads(convert(make_schedule_xlsx(), timezone=timezone))
    version = dt.datetime.fromisoformat(result["version"])
    assert version.tzinfo is not None
    assert version.utcoffset() is not None


def test_convert_version_uses_event_timezone():
    """When an event timezone is given, "version" carries that offset."""
    result = json.loads(convert(make_schedule_xlsx(), timezone="Europe/Berlin"))
    version = dt.datetime.fromisoformat(result["version"])
    assert version.utcoffset() in (dt.timedelta(hours=1), dt.timedelta(hours=2))
