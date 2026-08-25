from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import requests

from .canvas import CanvasItem
from .config import Config
from .planner import StudySession


@dataclass
class SyncStats:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


class NotionClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.notion_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        })
        self.base = "https://api.notion.com/v1"
        self.assignment_schema = self._schema(config.notion_database_id)
        self.plan_schema = self._schema(config.notion_plan_database_id)
        self.course_pages = self._course_pages()
        self._require(self.assignment_schema, (config.title_property, config.due_property,
                      config.source_id_property), "Assignments")
        self._require(self.plan_schema, ("Session", "Scheduled Date", "Source ID"),
                      "Daily Study Plan")

    def _schema(self, database_id: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base}/databases/{database_id}", timeout=30)
        response.raise_for_status()
        return response.json()["properties"]

    @staticmethod
    def _require(schema: dict[str, Any], names: tuple[str, ...], database: str) -> None:
        missing = [name for name in names if name not in schema]
        if missing:
            raise ValueError(f"{database} is missing required properties: {', '.join(missing)}")

    @staticmethod
    def _rich_text(value: str) -> dict[str, Any]:
        content = [{"type": "text", "text": {"content": value[:2000]}}] if value else []
        return {"rich_text": content}

    def _query_all(self, database_id: str) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = []
        cursor = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            response = self.session.post(
                f"{self.base}/databases/{database_id}/query", json=payload, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            pages.extend(data["results"])
            if not data.get("has_more"):
                return pages
            cursor = data["next_cursor"]

    @staticmethod
    def _plain_text(prop: dict[str, Any]) -> str:
        values = prop.get(prop.get("type", "rich_text"), [])
        return "".join(part.get("plain_text", "") for part in values)

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(value.casefold().replace("&", "and").split())

    def _course_pages(self) -> dict[str, str]:
        courses: dict[str, str] = {}
        for page in self._query_all(self.config.notion_courses_database_id):
            props = page.get("properties", {})
            for prop_name in ("Course Name", "Course Code"):
                value = self._plain_text(props.get(prop_name, {}))
                if value:
                    courses[self._normalized(value)] = page["id"]
        return courses

    def _course_relation(self, course: str) -> dict[str, Any] | None:
        normalized = self._normalized(course)
        page_id = self.course_pages.get(normalized)
        if not page_id:
            for key, candidate in self.course_pages.items():
                if normalized in key or key in normalized:
                    page_id = candidate
                    break
        return {"relation": [{"id": page_id}]} if page_id else None

    @staticmethod
    def _assignment_type(item: CanvasItem) -> str:
        text = f"{item.name} {item.description}".casefold()
        checks = (("exam", "Exam"), ("midterm", "Exam"), ("final", "Exam"),
                  ("quiz", "Quiz"), ("project", "Project"), ("reading", "Reading"),
                  ("discussion", "Discussion"))
        return next((kind for keyword, kind in checks if keyword in text), "Homework")

    def _existing(self, database_id: str, source_property: str) -> dict[str, dict[str, Any]]:
        existing: dict[str, dict[str, Any]] = {}
        for page in self._query_all(database_id):
            source = self._plain_text(page.get("properties", {}).get(source_property, {}))
            if source:
                existing[source] = page
        return existing

    def _write(self, database_id: str, current: dict[str, Any] | None,
               props: dict[str, Any]) -> dict[str, Any]:
        if current:
            response = self.session.patch(
                f"{self.base}/pages/{current['id']}", json={"properties": props}, timeout=30
            )
        else:
            response = self.session.post(
                f"{self.base}/pages",
                json={"parent": {"database_id": database_id}, "properties": props},
                timeout=30,
            )
        response.raise_for_status()
        return response.json()

    def sync_assignments(self, records: list[CanvasItem]) -> tuple[SyncStats, dict[str, str]]:
        c = self.config
        existing = self._existing(c.notion_database_id, c.source_id_property)
        stats = SyncStats()
        page_ids: dict[str, str] = {}
        for record in records:
            props: dict[str, Any] = {
                c.title_property: {"title": [{"text": {"content": record.name[:2000]}}]},
                c.due_property: {"date": {"start": record.due.isoformat()}},
                c.source_id_property: self._rich_text(record.source_id),
                "Sync Source": {"select": {"name": "Canvas Calendar" if record.source_id.startswith("canvas:") else "Syllabus"}},
                "Type": {"select": {"name": self._assignment_type(record)}},
            }
            relation = self._course_relation(record.course)
            if relation:
                props[c.course_property] = relation
            details = "\n".join(part for part in (record.description, record.url) if part)
            if details:
                props[c.notes_property] = self._rich_text(details)
            current = existing.get(record.source_id)
            page = self._write(c.notion_database_id, current, props)
            page_ids[record.source_id] = page["id"]
            if current:
                stats.updated += 1
            else:
                stats.created += 1
        return stats, page_ids

    @staticmethod
    def _plan_window(scheduled: date, today: date) -> str:
        if scheduled == today:
            return "Today"
        if scheduled == today + timedelta(days=1):
            return "Tomorrow"
        if scheduled <= today + timedelta(days=7):
            return "This Week"
        return "Later"

    def sync_plan(self, records: list[StudySession],
                  assignment_pages: dict[str, str]) -> SyncStats:
        database_id = self.config.notion_plan_database_id
        existing = self._existing(database_id, "Source ID")
        desired = {record.source_id for record in records}
        stats = SyncStats()
        for source, page in existing.items():
            if source.startswith(("study:", "work:")) and source not in desired:
                response = self.session.patch(
                    f"{self.base}/pages/{page['id']}", json={"archived": True}, timeout=30
                )
                response.raise_for_status()

        today = datetime.now(self.config.timezone).date()
        for record in records:
            why = f"{record.minutes} minutes"
            if record.optional:
                why += " · optional Friday/Saturday overflow"
            props: dict[str, Any] = {
                "Session": {"title": [{"text": {"content": record.name[:2000]}}]},
                "Scheduled Date": {"date": {"start": record.due.isoformat()}},
                "Minutes": {"number": record.minutes},
                "Session Type": {"select": {"name": "Exam Prep" if record.session_type == "Study Session" else "Complete Assignment"}},
                "Required": {"checkbox": not record.optional},
                "Plan Source": {"select": {"name": "Automatic"}},
                "Plan Window": {"select": {"name": self._plan_window(record.due.date(), today)}},
                "Why Today": self._rich_text(why),
                "Source ID": self._rich_text(record.source_id),
            }
            assignment_id = assignment_pages.get(record.assignment_source_id)
            if assignment_id:
                props["Assignment"] = {"relation": [{"id": assignment_id}]}
            current = existing.get(record.source_id)
            if not current:
                props["Status"] = {"select": {"name": "Planned"}}
            self._write(database_id, current, props)
            if current:
                stats.updated += 1
            else:
                stats.created += 1
        return stats
