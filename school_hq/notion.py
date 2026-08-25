from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
        )
        self.base = "https://api.notion.com/v1"
        response = self.session.get(f"{self.base}/databases/{config.notion_database_id}", timeout=30)
        response.raise_for_status()
        self.schema = response.json()["properties"]
        required = (
            config.title_property,
            config.due_property,
            config.source_id_property,
        )
        missing = [name for name in required if name not in self.schema]
        if missing:
            raise ValueError(
                "The Notion database is missing required properties: " + ", ".join(missing)
            )
        if self.schema[config.source_id_property]["type"] != "rich_text":
            raise ValueError(f"{config.source_id_property} must be a Text property")

    def _rich_text(self, value: str) -> dict[str, Any]:
        return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}] if value else []}

    def _select_or_text(self, property_name: str, value: str) -> dict[str, Any] | None:
        if not value or property_name not in self.schema:
            return None
        kind = self.schema[property_name]["type"]
        if kind == "select":
            return {"select": {"name": value[:100]}}
        if kind == "multi_select":
            return {"multi_select": [{"name": value[:100]}]}
        if kind == "rich_text":
            return self._rich_text(value)
        return None

    def _status(self, value: str) -> dict[str, Any] | None:
        name = self.config.status_property
        if name not in self.schema:
            return None
        kind = self.schema[name]["type"]
        if kind == "status":
            return {"status": {"name": value}}
        if kind == "select":
            return {"select": {"name": value}}
        return None

    def _base_properties(
        self, *, name: str, due: datetime, source_id: str, course: str, item_type: str
    ) -> dict[str, Any]:
        c = self.config
        properties: dict[str, Any] = {
            c.title_property: {"title": [{"text": {"content": name[:2000]}}]},
            c.due_property: {"date": {"start": due.isoformat()}},
        }
        optional = {
            c.source_id_property: self._rich_text(source_id),
            c.course_property: self._select_or_text(c.course_property, course),
            c.type_property: self._select_or_text(c.type_property, item_type),
            c.status_property: self._status("Not started"),
        }
        for prop_name, value in optional.items():
            if prop_name in self.schema and value is not None:
                properties[prop_name] = value
        return properties

    def _source_text(self, page: dict[str, Any]) -> str:
        prop = page.get("properties", {}).get(self.config.source_id_property, {})
        values = prop.get("rich_text", [])
        return "".join(part.get("plain_text", "") for part in values)

    def existing_by_source(self) -> dict[str, dict[str, Any]]:
        existing: dict[str, dict[str, Any]] = {}
        cursor = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            response = self.session.post(
                f"{self.base}/databases/{self.config.notion_database_id}/query",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            for page in data["results"]:
                source_id = self._source_text(page)
                if source_id:
                    existing[source_id] = page
            if not data.get("has_more"):
                return existing
            cursor = data["next_cursor"]

    def upsert(
        self,
        records: list[CanvasItem | StudySession],
        *,
        prune_prefix: str | None = None,
    ) -> SyncStats:
        existing = self.existing_by_source()
        stats = SyncStats()
        desired_ids = {record.source_id for record in records}
        if prune_prefix:
            for source_id, page in existing.items():
                if source_id.startswith(prune_prefix) and source_id not in desired_ids:
                    response = self.session.patch(
                        f"{self.base}/pages/{page['id']}",
                        json={"archived": True},
                        timeout=30,
                    )
                    response.raise_for_status()
        for record in records:
            if isinstance(record, CanvasItem):
                props = self._base_properties(
                    name=record.name,
                    due=record.due,
                    source_id=record.source_id,
                    course=record.course,
                    item_type="Assignment",
                )
                if self.config.notes_property in self.schema:
                    notes = "\n".join(part for part in (record.description, record.url) if part)
                    props[self.config.notes_property] = self._rich_text(notes)
            else:
                label = f"{record.minutes} minutes"
                if record.optional:
                    label += " · optional Friday/Saturday session"
                props = self._base_properties(
                    name=record.name,
                    due=record.due,
                    source_id=record.source_id,
                    course=record.course,
                    item_type="Study Session",
                )
                if self.config.notes_property in self.schema:
                    props[self.config.notes_property] = self._rich_text(label)
            current = existing.get(record.source_id)
            if current:
                # Never reset a user's completion/status choice during a refresh.
                props.pop(self.config.status_property, None)
                response = self.session.patch(
                    f"{self.base}/pages/{current['id']}", json={"properties": props}, timeout=30
                )
                response.raise_for_status()
                stats.updated += 1
            else:
                response = self.session.post(
                    f"{self.base}/pages",
                    json={
                        "parent": {"database_id": self.config.notion_database_id},
                        "properties": props,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                stats.created += 1
        return stats
