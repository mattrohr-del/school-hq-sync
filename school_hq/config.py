from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Config:
    canvas_ics_url: str
    notion_token: str
    notion_database_id: str
    timezone: ZoneInfo
    daily_minutes: int
    horizon_days: int
    optional_days: frozenset[int]
    excluded_courses: tuple[str, ...]
    title_property: str
    due_property: str
    status_property: str
    course_property: str
    type_property: str
    source_id_property: str
    notes_property: str

    @classmethod
    def from_env(cls) -> "Config":
        required = ("CANVAS_ICS_URL", "NOTION_TOKEN", "NOTION_DATABASE_ID")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        optional_days = frozenset(
            int(day) for day in _csv(os.getenv("OPTIONAL_STUDY_DAYS", "4,5"))
        )
        if not optional_days.issubset(range(7)):
            raise ValueError("OPTIONAL_STUDY_DAYS must contain weekday numbers 0-6")
        return cls(
            canvas_ics_url=os.environ["CANVAS_ICS_URL"],
            notion_token=os.environ["NOTION_TOKEN"],
            notion_database_id=os.environ["NOTION_DATABASE_ID"].replace("-", ""),
            timezone=ZoneInfo(os.getenv("TIMEZONE", "America/Chicago")),
            daily_minutes=int(os.getenv("DAILY_STUDY_MINUTES", "60")),
            horizon_days=int(os.getenv("PLANNING_HORIZON_DAYS", "14")),
            optional_days=optional_days,
            excluded_courses=_csv(os.getenv("EXCLUDED_COURSES", "Career Development")),
            title_property=os.getenv("NOTION_TITLE_PROPERTY", "Name"),
            due_property=os.getenv("NOTION_DUE_PROPERTY", "Due Date"),
            status_property=os.getenv("NOTION_STATUS_PROPERTY", "Status"),
            course_property=os.getenv("NOTION_COURSE_PROPERTY", "Course"),
            type_property=os.getenv("NOTION_TYPE_PROPERTY", "Type"),
            source_id_property=os.getenv("NOTION_SOURCE_ID_PROPERTY", "Source ID"),
            notes_property=os.getenv("NOTION_NOTES_PROPERTY", "Notes"),
        )

