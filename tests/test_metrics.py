import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.metrics import Metrics, hour_bucket, summarize
from core.user_store import UserStore


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def __call__(self):
        return self.moment


NOW = datetime(2026, 10, 22, 20, 30, tzinfo=timezone.utc)  # 1:30 PM Pacific


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "users.db"
        UserStore(self.db)  # creates the users table, like the bot does
        self.clock = Clock(NOW)
        self.metrics = Metrics(self.db, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_are_buffered_until_flush(self):
        self.metrics.incr("meal", "logged")
        self.assertEqual(summarize(self.db, now=NOW)["windows"]["24h"], {})
        self.metrics.flush()
        self.assertEqual(summarize(self.db, now=NOW)["windows"]["24h"]["meal"], {"logged": 1})

    def test_repeated_flushes_add_up(self):
        for _ in range(3):
            self.metrics.incr("dm", "LOG_MEAL")
            self.metrics.flush()
        self.assertEqual(summarize(self.db, now=NOW)["windows"]["24h"]["dm"]["LOG_MEAL"], 3)

    def test_windows_and_per_day(self):
        self.clock.moment = NOW - timedelta(days=3)
        self.metrics.incr("meal", "logged")
        self.clock.moment = NOW - timedelta(days=9)  # outside 7 days
        self.metrics.incr("meal", "logged")
        self.clock.moment = NOW
        self.metrics.incr("meal", "logged")
        self.metrics.flush()
        stats = summarize(self.db, now=NOW)
        self.assertEqual(stats["windows"]["24h"]["meal"]["logged"], 1)
        self.assertEqual(stats["windows"]["7d"]["meal"]["logged"], 2)
        self.assertEqual(sorted(stats["per_day"]), ["2026-10-19", "2026-10-22"])

    def test_quota_since_midnight_pacific_ignores_rejected_calls(self):
        self.clock.moment = NOW - timedelta(hours=14)  # 11:30 PM Pacific yesterday
        self.metrics.incr("ai_call", "gemini-3.6-flash:ok")
        self.clock.moment = NOW
        self.metrics.incr("ai_call", "gemini-3.6-flash:ok", 2)
        self.metrics.incr("ai_call", "gemini-3.6-flash:rate_limited")
        self.metrics.incr("ai_call", "gemini-3.5-flash:overloaded")
        self.metrics.flush()
        self.assertEqual(summarize(self.db, now=NOW)["quota_today"],
                         {"gemini-3.6-flash": 2, "gemini-3.5-flash": 1})

    def test_active_and_registered_users(self):
        store = UserStore(self.db)
        store.ensure_user("1", "Alex")
        store.ensure_user("2", "Sam")
        store.set_goals("1", {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70})
        self.metrics.seen_user(1)
        self.metrics.seen_user(1)
        self.clock.moment = NOW - timedelta(days=2)
        self.metrics.seen_user(2)
        self.metrics.flush()
        users = summarize(self.db, now=NOW)["users"]
        self.assertEqual((users["total"], users["with_goals"]), (2, 1))
        self.assertEqual((users["active_24h"], users["active_7d"]), (1, 2))

    def test_failed_flush_keeps_counts_for_next_time(self):
        self.metrics.incr("meal", "logged")
        real_path = self.metrics.database_path
        self.metrics.database_path = "/nonexistent/dir/db.sqlite"
        self.metrics.flush()  # must not raise
        self.metrics.database_path = real_path
        self.metrics.flush()
        self.assertEqual(summarize(self.db, now=NOW)["windows"]["24h"]["meal"]["logged"], 1)

    def test_hour_bucket_is_utc(self):
        self.assertEqual(hour_bucket(NOW), "2026-10-22T20")


if __name__ == "__main__":
    unittest.main()
