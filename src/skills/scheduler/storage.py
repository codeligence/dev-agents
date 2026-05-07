"""Schedule persistence via dev-agents BaseStorage.

Each schedule is stored as a separate key: ``schedule_{id}``.
An index key ``schedule_index`` tracks all schedule IDs for fast enumeration.
"""

from __future__ import annotations

from typing import Any
import time
import uuid

from core.log import get_logger
from core.storage import BaseStorage

logger = get_logger("skills.scheduler.storage")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class ScheduleEntry:
    """In-memory representation of a stored schedule."""

    __slots__ = (
        "id",
        "cron",
        "task",
        "origin_info",
        "enabled",
        "created_at",
    )

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.cron: str = data["cron"]
        self.task: str = data["task"]
        self.origin_info: dict[str, Any] = data["origin_info"]
        self.enabled: bool = data.get("enabled", True)
        self.created_at: float = data.get("created_at", time.time())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cron": self.cron,
            "task": self.task,
            "origin_info": self.origin_info,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class ScheduleStorage:
    """CRUD wrapper around BaseStorage for schedule entries."""

    KEY_PREFIX = "schedule_"
    INDEX_KEY = "schedule_index"

    def __init__(self, storage: BaseStorage) -> None:
        self._storage = storage

    def _key(self, schedule_id: str) -> str:
        return f"{self.KEY_PREFIX}{schedule_id}"

    def _load_index(self) -> list[str]:
        return self._storage.get(self.INDEX_KEY, [])

    def _save_index(self, ids: list[str]) -> None:
        self._storage.set(self.INDEX_KEY, ids)

    def create(self, data: dict[str, Any]) -> ScheduleEntry:
        """Create a new schedule. Returns the persisted entry."""
        data = {**data}
        schedule_id = _new_id()
        data["id"] = schedule_id
        data.setdefault("created_at", time.time())
        data.setdefault("enabled", True)

        entry = ScheduleEntry(data)
        self._storage.set(self._key(schedule_id), entry.to_dict())

        ids = self._load_index()
        ids.append(schedule_id)
        self._save_index(ids)

        logger.info(
            f"Created schedule {schedule_id}: {entry.cron} -> {entry.task[:60]}"
        )
        return entry

    def get(self, schedule_id: str) -> ScheduleEntry | None:
        raw = self._storage.get(self._key(schedule_id))
        if raw is None:
            return None
        return ScheduleEntry(raw)

    def list_all(self) -> list[ScheduleEntry]:
        entries: list[ScheduleEntry] = []
        for sid in self._load_index():
            entry = self.get(sid)
            if entry is not None:
                entries.append(entry)
        return entries

    def delete(self, schedule_id: str) -> bool:
        if self._storage.get(self._key(schedule_id)) is None:
            return False
        self._storage.delete(self._key(schedule_id))
        ids = self._load_index()
        ids = [i for i in ids if i != schedule_id]
        self._save_index(ids)
        logger.info(f"Deleted schedule {schedule_id}")
        return True
