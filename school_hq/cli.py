from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .canvas import fetch_calendar
from .config import Config
from .manual import load_manual_assignments
from .notion import NotionClient
from .planner import build_plan


def main() -> None:
    config = Config.from_env()
    now = datetime.now(config.timezone)
    canvas_assignments = fetch_calendar(config.canvas_ics_url, config.timezone)
    manual_assignments = load_manual_assignments(Path("data"), config.timezone)
    assignments = list(
        {item.source_id: item for item in canvas_assignments + manual_assignments}.values()
    )
    plan = build_plan(
        assignments,
        today=now.date(),
        daily_minutes=config.daily_minutes,
        test_study_minutes=config.test_study_minutes,
        horizon_days=config.horizon_days,
        optional_days=config.optional_days,
        excluded_courses=config.excluded_courses,
    )
    notion = NotionClient(config)
    assignment_stats, assignment_pages = notion.sync_assignments(assignments)
    study_stats = notion.sync_plan(plan, assignment_pages)
    print(
        f"Assignments: {assignment_stats.created} created, "
        f"{assignment_stats.updated} updated; "
        f"study plan: {study_stats.created} created, {study_stats.updated} updated."
    )


if __name__ == "__main__":
    main()
