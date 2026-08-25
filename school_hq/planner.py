from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .canvas import CanvasItem


@dataclass(frozen=True)
class StudySession:
    source_id: str
    name: str
    due: datetime
    course: str
    minutes: int
    optional: bool
    assignment_source_id: str


def _excluded(course: str, excluded_courses: tuple[str, ...]) -> bool:
    normalized = course.casefold()
    return any(excluded.casefold() in normalized for excluded in excluded_courses)


def build_plan(
    assignments: list[CanvasItem],
    today: date,
    daily_minutes: int = 60,
    horizon_days: int = 14,
    optional_days: frozenset[int] = frozenset({4, 5}),
    excluded_courses: tuple[str, ...] = ("Career Development",),
) -> list[StudySession]:
    """Create small, finite sessions without exceeding the daily study budget.

    Sessions are scheduled on the days before an assignment, prioritizing closer due
    dates. Friday and Saturday are fallback-only by default. Each assignment receives
    at most three 30-minute sessions; short/near work receives one.
    """
    eligible = [
        item
        for item in assignments
        if today <= item.due.date() <= today + timedelta(days=horizon_days)
        and not _excluded(item.course, excluded_courses)
    ]
    eligible.sort(key=lambda item: (item.due, item.course, item.name))
    capacity: dict[date, int] = {
        today + timedelta(days=offset): daily_minutes for offset in range(horizon_days + 1)
    }
    sessions: list[StudySession] = []

    for item in eligible:
        days_until_due = (item.due.date() - today).days
        target_sessions = 1 if days_until_due <= 2 else (2 if days_until_due <= 6 else 3)
        candidate_dates = [
            today + timedelta(days=offset)
            for offset in range(max(days_until_due, 1))
            if today + timedelta(days=offset) < item.due.date()
        ]
        if not candidate_dates and item.due.date() == today:
            candidate_dates = [today]
        normal = [day for day in candidate_dates if day.weekday() not in optional_days]
        fallback = [day for day in candidate_dates if day.weekday() in optional_days]
        # Spread work earlier while preserving optional days as overflow only.
        ordered = normal + fallback
        selected: list[date] = []
        for day in ordered:
            if capacity.get(day, 0) >= 30:
                selected.append(day)
                capacity[day] -= 30
                if len(selected) == target_sessions:
                    break
        for number, day in enumerate(selected, start=1):
            digest = hashlib.sha256(f"{item.source_id}|{day.isoformat()}".encode()).hexdigest()[:20]
            sessions.append(
                StudySession(
                    source_id=f"study:{digest}",
                    name=f"Study: {item.name}",
                    due=datetime.combine(day, datetime.min.time(), item.due.tzinfo).replace(hour=18),
                    course=item.course,
                    minutes=30,
                    optional=day.weekday() in optional_days,
                    assignment_source_id=item.source_id,
                )
            )
    return sorted(sessions, key=lambda session: (session.due, session.course, session.name))

