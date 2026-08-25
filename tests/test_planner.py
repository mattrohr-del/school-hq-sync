from datetime import date, datetime
from zoneinfo import ZoneInfo

from school_hq.canvas import CanvasItem
from school_hq.planner import build_plan


TZ = ZoneInfo("America/Chicago")


def assignment(name: str, course: str, due_day: int) -> CanvasItem:
    return CanvasItem(
        source_id=f"canvas:{name}",
        name=name,
        due=datetime(2026, 8, due_day, 23, 59, tzinfo=TZ),
        course=course,
        description="",
        url="",
    )


def test_plan_respects_daily_hour_and_avoids_optional_days_when_possible():
    plan = build_plan(
        [assignment("Exam", "M300", 31), assignment("Quiz", "C200", 30)],
        today=date(2026, 8, 24),
    )
    minutes = {}
    for session in plan:
        minutes[session.due.date()] = minutes.get(session.due.date(), 0) + session.minutes
    assert all(total <= 60 for total in minutes.values())
    assert all(session.due.weekday() not in {4, 5} for session in plan)


def test_excludes_career_development():
    plan = build_plan(
        [assignment("Reflection", "Career Development", 28)],
        today=date(2026, 8, 24),
    )
    assert plan == []


def test_near_assignment_gets_one_small_action():
    plan = build_plan([assignment("Quiz", "C200", 26)], today=date(2026, 8, 24))
    assert len(plan) == 1
    assert plan[0].minutes == 30

