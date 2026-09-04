"""Tests for the conversation scoping that gates the agent-facing tools.

Schedules carry the origin of the conversation that created them, and firing
one posts back into it. These helpers are the authorization boundary: without
them, anyone who can talk to the bot in one channel can read, delete, or aim
output at schedules belonging to another.
"""

from unittest.mock import MagicMock, patch

import pytest

from skills.scheduler import skill
from skills.scheduler.storage import ScheduleStorage


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


PUBLIC = {"type": "slack", "channel_id": "C-public"}
PRIVATE = {"type": "slack", "channel_id": "C-private"}


@pytest.fixture()
def scheduler(monkeypatch):
    """Wire the skill's module-level singletons to in-memory doubles."""
    storage = ScheduleStorage(FakeStorage())
    monkeypatch.setattr(skill, "_storage", storage)
    monkeypatch.setattr(skill, "_service", MagicMock())
    return storage


def _create(storage, origin_info, task="do a thing"):
    return storage.create(
        {"cron": "0 9 * * *", "task": task, "origin_info": origin_info}
    ).id


class TestConversationKey:
    def test_same_channel_matches(self):
        assert skill._conversation_key(PUBLIC) == skill._conversation_key(dict(PUBLIC))

    def test_different_channel_differs(self):
        assert skill._conversation_key(PUBLIC) != skill._conversation_key(PRIVATE)

    def test_same_channel_different_thread_matches(self):
        """Schedules belong to a channel, not to the thread that made them."""
        threaded = {**PUBLIC, "thread_ts": "1779839096.711709"}
        assert skill._conversation_key(PUBLIC) == skill._conversation_key(threaded)

    def test_same_channel_id_across_platforms_differs(self):
        assert skill._conversation_key({"type": "slack", "channel_id": "X"}) != (
            skill._conversation_key({"type": "mattermost", "channel_id": "X"})
        )

    def test_missing_fields_do_not_collide_with_a_real_channel(self):
        assert skill._conversation_key({}) != skill._conversation_key(PUBLIC)


class TestSchedulesInScope:
    def test_only_own_conversation_returned(self, scheduler):
        mine = _create(scheduler, PUBLIC, task="public task")
        _create(scheduler, PRIVATE, task="secret board briefing")

        visible = skill.schedules_in_scope(PUBLIC)

        assert [e["id"] for e in visible] == [mine]
        assert "secret board briefing" not in str(visible)

    def test_empty_when_conversation_has_none(self, scheduler):
        _create(scheduler, PRIVATE)
        assert skill.schedules_in_scope(PUBLIC) == []

    def test_unscoped_list_still_sees_everything(self, scheduler):
        """The scheduler service itself must keep seeing all schedules."""
        _create(scheduler, PUBLIC)
        _create(scheduler, PRIVATE)
        assert len(skill.list_schedules()) == 2


class TestDeleteScheduleInScope:
    def test_deletes_own_schedule(self, scheduler):
        schedule_id = _create(scheduler, PUBLIC)
        assert skill.delete_schedule_in_scope(schedule_id, PUBLIC) is True
        assert skill.get_schedule(schedule_id) is None

    def test_refuses_other_conversation(self, scheduler):
        schedule_id = _create(scheduler, PRIVATE)

        assert skill.delete_schedule_in_scope(schedule_id, PUBLIC) is False
        assert skill.get_schedule(schedule_id) is not None

    @pytest.mark.usefixtures("scheduler")
    def test_missing_schedule_returns_false(self):
        assert skill.delete_schedule_in_scope("does-not-exist", PUBLIC) is False

    def test_refusal_does_not_reach_the_scheduler(self, scheduler):
        """An out-of-scope delete must not unload the job either."""
        schedule_id = _create(scheduler, PRIVATE)

        with patch.object(skill, "delete_schedule") as unscoped_delete:
            skill.delete_schedule_in_scope(schedule_id, PUBLIC)

        unscoped_delete.assert_not_called()


class TestUninitialisedScheduler:
    """With no storage wired up the helpers must fail closed, not explode."""

    def test_get_schedule(self, monkeypatch):
        monkeypatch.setattr(skill, "_storage", None)
        assert skill.get_schedule("abc") is None

    def test_schedules_in_scope(self, monkeypatch):
        monkeypatch.setattr(skill, "_storage", None)
        assert skill.schedules_in_scope(PUBLIC) == []

    def test_delete_in_scope(self, monkeypatch):
        monkeypatch.setattr(skill, "_storage", None)
        assert skill.delete_schedule_in_scope("abc", PUBLIC) is False
