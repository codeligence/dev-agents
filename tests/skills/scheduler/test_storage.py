"""Tests for skills.scheduler.storage — ScheduleEntry and ScheduleStorage."""

import pytest

from skills.scheduler.storage import ScheduleEntry, ScheduleStorage


class FakeStorage:
    """Minimal in-memory BaseStorage implementation for testing."""

    def __init__(self):
        self._data: dict = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False


@pytest.fixture()
def storage():
    return ScheduleStorage(FakeStorage())


class TestScheduleEntry:
    def test_roundtrip(self):
        data = {
            "id": "abc123",
            "cron": "*/5 * * * *",
            "task": "do stuff",
            "origin_info": {"type": "slack", "channel_id": "C123"},
        }
        entry = ScheduleEntry(data)
        assert entry.id == "abc123"
        assert entry.cron == "*/5 * * * *"
        assert entry.task == "do stuff"
        assert entry.origin_info == {"type": "slack", "channel_id": "C123"}
        assert entry.enabled is True

        d = entry.to_dict()
        assert d["id"] == "abc123"
        assert d["cron"] == "*/5 * * * *"
        assert d["origin_info"]["type"] == "slack"

    def test_defaults(self):
        entry = ScheduleEntry(
            {
                "id": "x",
                "cron": "0 0 * * *",
                "task": "t",
                "origin_info": {"type": "cli"},
            }
        )
        assert entry.enabled is True
        assert isinstance(entry.created_at, float)


class TestScheduleStorageCreate:
    def test_create_assigns_id(self, storage):
        entry = storage.create(
            {
                "cron": "0 9 * * 1",
                "task": "weekly",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        assert len(entry.id) == 12
        assert entry.cron == "0 9 * * 1"
        assert entry.task == "weekly"

    def test_create_persists(self, storage):
        entry = storage.create(
            {
                "cron": "0 0 * * *",
                "task": "daily",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        retrieved = storage.get(entry.id)
        assert retrieved is not None
        assert retrieved.id == entry.id
        assert retrieved.task == "daily"


class TestScheduleStorageListAll:
    def test_empty_list(self, storage):
        assert storage.list_all() == []

    def test_lists_created_entries(self, storage):
        storage.create(
            {
                "cron": "0 0 * * *",
                "task": "a",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        storage.create(
            {
                "cron": "0 12 * * *",
                "task": "b",
                "origin_info": {"type": "slack", "channel_id": "C2"},
            }
        )
        entries = storage.list_all()
        assert len(entries) == 2
        tasks = {e.task for e in entries}
        assert tasks == {"a", "b"}


class TestScheduleStorageDelete:
    def test_delete_existing(self, storage):
        entry = storage.create(
            {
                "cron": "0 0 * * *",
                "task": "t",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        assert storage.delete(entry.id) is True
        assert storage.get(entry.id) is None
        assert storage.list_all() == []

    def test_delete_nonexistent(self, storage):
        assert storage.delete("nonexistent") is False

    def test_delete_removes_from_index(self, storage):
        e1 = storage.create(
            {
                "cron": "0 0 * * *",
                "task": "a",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        e2 = storage.create(
            {
                "cron": "0 12 * * *",
                "task": "b",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        storage.delete(e1.id)
        remaining = storage.list_all()
        assert len(remaining) == 1
        assert remaining[0].id == e2.id


class TestScheduleStorageGet:
    def test_get_nonexistent(self, storage):
        assert storage.get("no_such_id") is None
