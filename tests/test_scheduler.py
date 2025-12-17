"""Tests for scheduler helper logic."""

from datetime import datetime, timedelta, timezone

from worker.scheduler import is_template_due


class DummyTemplate:
    def __init__(self, last_run_at, frequency_hours):
        self.last_run_at = last_run_at
        self.frequency_hours = frequency_hours


def test_due_when_never_run():
    template = DummyTemplate(last_run_at=None, frequency_hours=6)
    now = datetime.now(tz=timezone.utc)
    assert is_template_due(template, now)


def test_not_due_before_interval():
    now = datetime.now(tz=timezone.utc)
    template = DummyTemplate(last_run_at=now - timedelta(hours=5), frequency_hours=6)
    assert not is_template_due(template, now)


def test_due_after_interval():
    now = datetime.now(tz=timezone.utc)
    template = DummyTemplate(last_run_at=now - timedelta(hours=7), frequency_hours=6)
    assert is_template_due(template, now)



