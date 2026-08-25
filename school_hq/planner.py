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
    session_type: str


ASSESSMENT_KEYWORDS = ("exam", "test", "midterm", "final")


def _excluded(course: str, excluded_courses: tuple[str, ...]) -> bool:
    normalized = course.casefold()
    return any(excluded.casefold() in normalized for excluded in excluded_courses)


def _is_assessment(item: CanvasItem) -> bool:
    text = f"{item.name} {item.description}".casefold()
    return any(keyword in text for keyword in ASSESSMENT_KEYWORDS)


def build_plan(
    assignments: list[CanvasItem],
    today: date,
    daily_minutes: int = 60,
    test_study_minutes: int = 20,
    horizon_days: int = 14,
    optional_days: frozenset[int] = frozenset({4, 5}),
    excluded_courses: tuple[str, ...] = ("Career Development",),
) -> list[StudySession]:
    """Create homework sessions plus a separate daily test-study habit.

    Homework receives one to three 30-minute work sessions within the daily homework
    budget. When an assessment is approaching, the closest assessment receives one
    additional 20-minute study session on every normal study day. Test study does not
    consume homework capacity. Friday and Saturday remain optional.
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

    homework = [item for item in eligible if not _is_assessment(item)]
    assessments = [item for item in eligible if _is_assessment(item)]

    for item in homework:
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
                    source_id=f"work:{digest}",
                    name=f"Work on: {item.name}",
                    # Homework comes first in the daily plan.
                    due=datetime.combine(day, datetime.min.time(), item.due.tzinfo).replace(hour=17),
                    course=item.course,
                    minutes=30,
                    optional=day.weekday() in optional_days,
                    assignment_source_id=item.source_id,
                    session_type="Work Session",
                )
            )

    # Add exactly one 20-minute test-study block per normal day. If multiple
    # assessments are coming up, focus on the closest one first.
    for offset in range(horizon_days + 1):
        day = today + timedelta(days=offset)
        if day.weekday() in optional_days:
            continue
        upcoming = [item for item in assessments if day < item.due.date()]
        if not upcoming:
            continue
        item = min(upcoming, key=lambda candidate: candidate.due)
        digest = hashlib.sha256(
            f"test-study|{item.source_id}|{day.isoformat()}".encode()
        ).hexdigest()[:20]
        sessions.append(
            StudySession(
                source_id=f"study:{digest}",
                name=f"Study for: {item.name}",
                # Test study follows the normal homework/work block.
                due=datetime.combine(day, datetime.min.time(), item.due.tzinfo).replace(
                    hour=18, minute=15
                ),
                course=item.course,
                minutes=test_study_minutes,
                optional=False,
                assignment_source_id=item.source_id,
                session_type="Study Session",
            )
        )
    return sorted(sessions, key=lambda session: (session.due, session.course, session.name))
