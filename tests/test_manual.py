from pathlib import Path
from zoneinfo import ZoneInfo

from school_hq.manual import load_manual_assignments


def test_loads_personal_health_schedule():
    assignments = load_manual_assignments(Path("data"), ZoneInfo("America/Chicago"))
    personal_health = [item for item in assignments if item.course == "Personal Health"]
    assert len(personal_health) == 45
    assert personal_health[0].name == "Module 1 — Written Reflection"
    assert personal_health[0].due.date().isoformat() == "2026-08-30"
    assert personal_health[-1].name == "Module 15 — Homework"
    assert personal_health[-1].due.date().isoformat() == "2026-12-13"
