"""Tests for handoff logic (offline, no DB required)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.bot.handoff import is_in_handoff_pause, should_resume, SHORT_PAUSE_HOURS, LONG_PAUSE_HOURS


def make_conv(**kwargs):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "external_thread_id": "123",
        "in_handoff": False,
        "handoff_at": None,
        "handoff_expires_at": None,
        "handoff_rule": None,
        "state": "active",
    }
    defaults.update(kwargs)
    return defaults


def now():
    return datetime.now(timezone.utc)


class TestIsInHandoffPause:
    def test_not_in_handoff_returns_false(self):
        conv = make_conv(in_handoff=False)
        assert is_in_handoff_pause(conv) is False

    def test_in_handoff_no_expiry_returns_true(self):
        conv = make_conv(in_handoff=True, handoff_expires_at=None)
        assert is_in_handoff_pause(conv) is True

    def test_in_handoff_future_expiry_returns_true(self):
        future = now() + timedelta(hours=6)
        conv = make_conv(in_handoff=True, handoff_expires_at=future)
        assert is_in_handoff_pause(conv) is True

    def test_in_handoff_past_expiry_returns_false(self):
        past = now() - timedelta(hours=1)
        conv = make_conv(in_handoff=True, handoff_expires_at=past)
        assert is_in_handoff_pause(conv) is False


class TestShouldResume:
    def test_not_in_handoff_returns_false(self):
        conv = make_conv(in_handoff=False, handoff_at=None)
        assert should_resume(conv) is False

    def test_recent_handoff_returns_false(self):
        recent = now() - timedelta(hours=1)
        conv = make_conv(in_handoff=True, handoff_at=recent)
        assert should_resume(conv) is False

    def test_old_handoff_returns_true(self):
        old = now() - timedelta(hours=LONG_PAUSE_HOURS + 1)
        conv = make_conv(in_handoff=True, handoff_at=old)
        assert should_resume(conv) is True

    def test_just_under_boundary_returns_false(self):
        just_before = now() - timedelta(hours=LONG_PAUSE_HOURS - 1)
        conv = make_conv(in_handoff=True, handoff_at=just_before)
        assert should_resume(conv) is False
