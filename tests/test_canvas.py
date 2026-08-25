from zoneinfo import ZoneInfo

from school_hq.canvas import parse_calendar


ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:assignment-42
DTSTART:20260902T215900Z
SUMMARY:Marketing Case Brief [M300-01195]
DESCRIPTION:Read the case and submit a response.
URL:https://iu.instructure.com/calendar?event_id=42
END:VEVENT
END:VCALENDAR
"""


def test_parse_canvas_item():
    item = parse_calendar(ICS, ZoneInfo("America/Chicago"))[0]
    assert item.source_id == "canvas:assignment-42"
    assert item.name == "Marketing Case Brief"
    assert item.course == "M300-01195"
    assert item.due.hour == 16

