"""Usage counters for the health report (deploy/health.sh).

The bot calls `incr()` and `seen_user()` as things happen; counts are kept in
memory and written to SQLite by `flush()` (the bot flushes once a minute), so
handling a message never waits on a database write. Counts are grouped by
UTC hour, which lets the report show any window (last 24 hours, last 7 days).

Metric names and labels:
    dm        intent (LOG_MEAL, SHOW_TODAY, ..., OTHER)
    command   slash command ("today", "goals set", "edit", ...)
    button    summary button ("today", "week")
    meal      "logged", "edited", "deleted"
    refused   "not_member", "rate_limited"
    welcome   "sent", "dms_closed", "failed" (guide DMed to new server members)
    ai_call   "<model>:ok", "<model>:overloaded", "<model>:rate_limited", "<model>:error"
    request   "answered", "all_busy", "unreadable", "error"
"""

import logging
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    bucket TEXT NOT NULL,          -- UTC hour, e.g. 2026-10-22T18
    name TEXT NOT NULL,
    label TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (bucket, name, label)
);
CREATE TABLE IF NOT EXISTS user_activity (
    bucket TEXT NOT NULL,          -- UTC hour
    discord_id TEXT NOT NULL,
    PRIMARY KEY (bucket, discord_id)
);
"""


def hour_bucket(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def bucket_start(bucket):
    return datetime.strptime(bucket, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


class Metrics:
    def __init__(self, database_path, clock=lambda: datetime.now(timezone.utc)):
        self.database_path = database_path
        self.clock = clock
        self._lock = threading.Lock()
        self._counts = Counter()
        self._users = set()
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(SCHEMA)

    def incr(self, name, label, amount=1):
        with self._lock:
            self._counts[(hour_bucket(self.clock()), name, str(label))] += amount

    def seen_user(self, discord_id):
        with self._lock:
            self._users.add((hour_bucket(self.clock()), str(discord_id)))

    def flush(self):
        """Write buffered counts to SQLite. Never raises: stats must not break the bot."""
        with self._lock:
            counts, users = self._counts, self._users
            self._counts, self._users = Counter(), set()
        if not counts and not users:
            return
        try:
            with sqlite3.connect(self.database_path) as connection:
                connection.executemany(
                    "INSERT INTO metrics (bucket, name, label, count) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (bucket, name, label) DO UPDATE SET count = count + excluded.count",
                    [(*key, value) for key, value in counts.items()],
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO user_activity (bucket, discord_id) VALUES (?, ?)",
                    list(users),
                )
        except sqlite3.Error:
            logger.exception("Could not save usage metrics; they will be retried")
            with self._lock:
                self._counts.update(counts)
                self._users.update(users)


def summarize(database_path, now=None, tz_name="America/Los_Angeles"):
    """Usage numbers for the health report, as plain dicts (JSON-friendly)."""
    now = now or datetime.now(timezone.utc)
    local = ZoneInfo(tz_name)
    since_24h = hour_bucket(now - timedelta(hours=24))
    since_7d = hour_bucket(now - timedelta(days=7))
    # Gemini's free-tier daily quota resets at midnight Pacific.
    local_midnight = now.astimezone(local).replace(hour=0, minute=0, second=0, microsecond=0)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)  # report works even before the bot has flushed
        rows = connection.execute(
            "SELECT bucket, name, label, count FROM metrics WHERE bucket >= ?", (since_7d,)
        ).fetchall()
        users = connection.execute(
            "SELECT COUNT(*), "
            "SUM(goals_json IS NOT NULL AND goals_json != ''), "
            "SUM(timezone IS NOT NULL AND timezone != '') FROM users"
        ).fetchone()
        active_24h = connection.execute(
            "SELECT COUNT(DISTINCT discord_id) FROM user_activity WHERE bucket >= ?", (since_24h,)
        ).fetchone()[0]
        active_7d = connection.execute(
            "SELECT COUNT(DISTINCT discord_id) FROM user_activity WHERE bucket >= ?", (since_7d,)
        ).fetchone()[0]

    windows = {"24h": {}, "7d": {}}
    per_day = {}
    quota_today = Counter()
    for bucket, name, label, count in rows:
        for window, since in (("24h", since_24h), ("7d", since_7d)):
            if bucket >= since:
                windows[window].setdefault(name, Counter())[label] += count
        start = bucket_start(bucket)
        day = start.astimezone(local).date().isoformat()
        per_day.setdefault(day, {}).setdefault(name, Counter())[label] += count
        if name == "ai_call" and start >= local_midnight.astimezone(timezone.utc):
            model, _, outcome = label.rpartition(":")
            if outcome != "rate_limited":  # rejected requests don't use quota
                quota_today[model] += count

    return {
        "users": {
            "total": users[0] or 0,
            "with_goals": users[1] or 0,
            "with_timezone": users[2] or 0,
            "active_24h": active_24h,
            "active_7d": active_7d,
        },
        "windows": {window: {name: dict(labels) for name, labels in names.items()}
                    for window, names in windows.items()},
        "per_day": {day: {name: dict(labels) for name, labels in names.items()}
                    for day, names in sorted(per_day.items())},
        "quota_today": dict(quota_today),
    }
