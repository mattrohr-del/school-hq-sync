from __future__ import annotations

from datetime import datetime

from .canvas import fetch_calendar
from .config import Config
from .notion import NotionClient
from .planner import build_plan


def main() -> None:
    config = Config.from_env()
    now = datetime.now(config.timezone)
    assignments = fetch_calendar(config.canvas_ics_url, config.timezone)
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
    assignment_stats = notion.upsert(assignments)
    study_stats = notion.upsert(plan, prune_prefix="study:")
    print(
        f"Canvas: {assignment_stats.created} created, {assignment_stats.updated} updated; "
        f"study plan: {study_stats.created} created, {study_stats.updated} updated."
    )


if __name__ == "__main__":
    main()
