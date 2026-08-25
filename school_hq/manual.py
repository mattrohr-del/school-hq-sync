from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .canvas import CanvasItem


TASK_SLUGS = {
    "Written Reflection": "reflection",
    "Quiz": "quiz",
    "Homework": "homework",
}


def load_manual_assignments(data_directory: Path, timezone: ZoneInfo) -> list[CanvasItem]:
    assignments: list[CanvasItem] = []
    if not data_directory.exists():
        return assignments
    for path in sorted(data_directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        course = data["course"]
        course_slug = path.stem.replace("_", "-")
        for module in data["modules"]:
            due = datetime.combine(
                datetime.fromisoformat(module["due"]).date(), time(23, 59), timezone
            )
            for task_name, objective in module["objectives"].items():
                task_slug = TASK_SLUGS.get(
                    task_name, task_name.casefold().replace(" ", "-")
                )
                assignments.append(
                    CanvasItem(
                        source_id=(
                            f"manual:{course_slug}:m{module['module']:02d}:{task_slug}"
                        ),
                        name=f"Module {module['module']} — {task_name}",
                        due=due,
                        course=course,
                        description=(
                            f"{module['chapter']} · Learning Objective {objective}"
                        ),
                        url="",
                    )
                )
    return assignments
