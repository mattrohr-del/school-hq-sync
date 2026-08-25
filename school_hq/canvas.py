from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar


@dataclass(frozen=True)
class CanvasItem:
    source_id: str
    name: str
    due: datetime
    course: str
    description: str
    url: str


COURSE_SUFFIX = re.compile(r"\s*\[(?P<course>[^\]]+)\]\s*$")


def _text(value: object) -> str:
    return str(value) if value is not None else ""


def _due(value: date | datetime, timezone: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone)
        return value.astimezone(timezone)
    return datetime.combine(value, time(23, 59), timezone)


def parse_calendar(raw: bytes, timezone: ZoneInfo) -> list[CanvasItem]:
    calendar = Calendar.from_ical(raw)
    items: list[CanvasItem] = []
    for event in calendar.walk("VEVENT"):
        summary = _text(event.get("SUMMARY")).strip()
        match = COURSE_SUFFIX.search(summary)
        course = match.group("course").strip() if match else ""
        name = summary[: match.start()].strip() if match else summary
        start = event.decoded("DTSTART")
        uid = _text(event.get("UID")).strip()
        url = _text(event.get("URL")).strip()
        description = _text(event.get("DESCRIPTION")).strip()
        if not uid:
            uid = hashlib.sha256(f"{summary}|{start}|{url}".encode()).hexdigest()
        items.append(
            CanvasItem(
                source_id=f"canvas:{uid}",
                name=name or "Canvas item",
                due=_due(start, timezone),
                course=course,
                description=description,
                url=url,
            )
        )
    return items


def fetch_calendar(url: str, timezone: ZoneInfo) -> list[CanvasItem]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return parse_calendar(response.content, timezone)

