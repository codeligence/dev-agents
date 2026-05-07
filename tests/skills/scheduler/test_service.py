"""Tests for skills.scheduler.service — SchedulerService and validate_cron."""

from unittest.mock import MagicMock, patch

import pytest

from skills.scheduler.service import SchedulerService, validate_cron
from skills.scheduler.storage import ScheduleEntry, ScheduleStorage


class FakeStorage:
    """Minimal in-memory BaseStorage for testing."""

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
def schedule_storage():
    return ScheduleStorage(FakeStorage())


@pytest.fixture()
def service(schedule_storage):
    svc = SchedulerService(schedule_storage=schedule_storage)
    return svc


class TestValidateCron:
    def test_valid_expression(self):
        trigger = validate_cron("*/5 * * * *")
        assert trigger is not None

    def test_invalid_expression_raises(self):
        with pytest.raises(ValueError):
            validate_cron("not a cron")

    def test_six_fields_raises(self):
        with pytest.raises(ValueError):
            validate_cron("* * * * * *")


class TestSchedulerServiceLifecycle:
    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_start_calls_scheduler_start(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        svc.start()

        mock_scheduler.start.assert_called_once()

    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_shutdown_calls_scheduler_shutdown(
        self, mock_scheduler_cls, schedule_storage
    ):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        svc.start()
        svc.shutdown()

        mock_scheduler.shutdown.assert_called_once_with(wait=False)

    def test_set_agent_service(self, service):
        mock_agent_service = MagicMock()
        service.set_agent_service(mock_agent_service)
        assert service._agent_service is mock_agent_service


class TestSchedulerServiceAddRemove:
    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_add_schedule_registers_job(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        entry = ScheduleEntry(
            {
                "id": "test123",
                "cron": "0 9 * * 1",
                "task": "test task",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )

        svc.add_schedule(entry)

        mock_scheduler.add_job.assert_called()
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs.kwargs["id"] == "schedule_test123"
        assert call_kwargs.kwargs["replace_existing"] is True

    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_remove_schedule_removes_job(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        svc.remove_schedule("test123")

        mock_scheduler.remove_job.assert_called_once_with("schedule_test123")

    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_add_invalid_cron_skipped(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        entry = ScheduleEntry(
            {
                "id": "bad_cron",
                "cron": "not valid",
                "task": "test",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )
        # Should not raise, just log error
        svc._add_job(entry)
        # add_job should not be called for invalid cron
        mock_scheduler.add_job.assert_not_called()


class TestSchedulerServiceSync:
    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_sync_adds_new_schedules(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_scheduler_cls.return_value = mock_scheduler

        # Create a schedule in storage
        schedule_storage.create(
            {
                "cron": "0 9 * * *",
                "task": "daily task",
                "origin_info": {"type": "slack", "channel_id": "C1"},
            }
        )

        svc = SchedulerService(schedule_storage=schedule_storage)
        svc._sync_from_storage()

        # Should have called add_job for the new schedule
        assert mock_scheduler.add_job.called

    @patch("skills.scheduler.service.BackgroundScheduler")
    def test_sync_removes_deleted_schedules(self, mock_scheduler_cls, schedule_storage):
        mock_scheduler = MagicMock()
        # Simulate a job loaded in APScheduler that no longer exists in storage
        mock_job = MagicMock()
        mock_job.id = "schedule_old_id"
        mock_scheduler.get_jobs.return_value = [mock_job]
        mock_scheduler_cls.return_value = mock_scheduler

        svc = SchedulerService(schedule_storage=schedule_storage)
        svc._sync_from_storage()

        mock_scheduler.remove_job.assert_called_with("schedule_old_id")
