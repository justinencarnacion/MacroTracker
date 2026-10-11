import json
import os
import sqlite3
from pathlib import Path


DEFAULT_DATABASE = Path(os.getenv("DB_PATH", Path("data") / "user_data.db"))

# Columns written by _upsert, in INSERT order (discord_id is handled separately).
COLUMNS = (
    "display_name",
    "token_json",
    "spreadsheet_id",
    "worksheet_id",
    "tab_mode",
    "goals_json",
    "timezone",
    "reminders_enabled",
    "reminder_times_json",
    "pending_confirmation_json",
)


class UserStore:
    def __init__(self, database_path=DEFAULT_DATABASE):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    token_json TEXT,
                    spreadsheet_id TEXT,
                    worksheet_id INTEGER,
                    tab_mode TEXT NOT NULL DEFAULT 'monthly',
                    goals_json TEXT,
                    timezone TEXT,
                    reminders_enabled INTEGER NOT NULL DEFAULT 0,
                    reminder_times_json TEXT,
                    pending_confirmation_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(users)")
            }
            migrations = {
                "worksheet_id": "ALTER TABLE users ADD COLUMN worksheet_id INTEGER",
                "goals_json": "ALTER TABLE users ADD COLUMN goals_json TEXT",
                "timezone": "ALTER TABLE users ADD COLUMN timezone TEXT",
                "reminders_enabled": (
                    "ALTER TABLE users ADD COLUMN reminders_enabled "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                "reminder_times_json": (
                    "ALTER TABLE users ADD COLUMN reminder_times_json TEXT"
                ),
                "pending_confirmation_json": (
                    "ALTER TABLE users ADD COLUMN pending_confirmation_json TEXT"
                ),
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

    def get(self, discord_id):
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"SELECT discord_id, {', '.join(COLUMNS)} FROM users WHERE discord_id = ?",
                (str(discord_id),),
            ).fetchone()
        if row is None:
            return None
        return {
            "discord_id": row["discord_id"],
            "display_name": row["display_name"],
            "token_json": row["token_json"],
            "spreadsheet_id": row["spreadsheet_id"],
            "worksheet_id": row["worksheet_id"],
            "tab_mode": row["tab_mode"],
            "goals": self._deserialize_json(row["goals_json"]),
            "timezone": row["timezone"],
            "reminders_enabled": bool(row["reminders_enabled"]),
            "reminder_times": self._deserialize_json(row["reminder_times_json"]) or [],
            "pending_confirmation": self._deserialize_json(
                row["pending_confirmation_json"]
            ),
        }

    def ensure_user(self, discord_id, display_name):
        """Create the user if missing and keep their display name current."""
        user = self.get(discord_id)
        if user is None or user["display_name"] != display_name:
            self._upsert(discord_id, display_name)
            user = self.get(discord_id)
        return user

    def upsert_token(self, discord_id, display_name, token_json):
        self._upsert(discord_id, display_name, token_json=token_json)

    def set_spreadsheet(self, discord_id, spreadsheet_id):
        self._upsert(discord_id, spreadsheet_id=spreadsheet_id)

    def set_worksheet_id(self, discord_id, worksheet_id):
        self._upsert(discord_id, worksheet_id=worksheet_id)

    def set_tab_mode(self, discord_id, tab_mode):
        self._upsert(discord_id, tab_mode=tab_mode)

    def set_goals(self, discord_id, goals):
        self._upsert(discord_id, goals_json=self._serialize_json(goals))

    def set_timezone(self, discord_id, timezone):
        self._upsert(discord_id, timezone=timezone)

    def set_reminders(self, discord_id, enabled, times):
        self._upsert(
            discord_id,
            reminders_enabled=int(enabled),
            reminder_times_json=self._serialize_json(times),
        )

    def set_pending_confirmation(self, discord_id, confirmation):
        self._upsert(
            discord_id,
            pending_confirmation_json=self._serialize_json(confirmation)
            if confirmation is not None
            else "",
        )

    def _upsert(self, discord_id, display_name=None, **fields):
        unknown = set(fields) - set(COLUMNS)
        if unknown:
            raise ValueError(f"Unknown user fields: {sorted(unknown)}")

        existing = self.get(discord_id)
        if existing is None:
            values = {column: None for column in COLUMNS}
            values.update(
                display_name=display_name or str(discord_id),
                tab_mode="monthly",
                reminders_enabled=0,
            )
        else:
            values = {
                "display_name": existing["display_name"],
                "token_json": existing["token_json"],
                "spreadsheet_id": existing["spreadsheet_id"],
                "worksheet_id": existing["worksheet_id"],
                "tab_mode": existing["tab_mode"],
                "goals_json": self._serialize_json(existing["goals"]),
                "timezone": existing["timezone"],
                "reminders_enabled": int(existing["reminders_enabled"]),
                "reminder_times_json": self._serialize_json(
                    existing["reminder_times"]
                ),
                "pending_confirmation_json": self._serialize_json(
                    existing["pending_confirmation"]
                ),
            }
        values.update({key: value for key, value in fields.items() if value is not None})
        if display_name is not None:
            values["display_name"] = display_name

        placeholders = ", ".join("?" for _ in range(len(COLUMNS) + 1))
        updates = ",\n".join(f"{column} = excluded.{column}" for column in COLUMNS)
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO users (discord_id, {', '.join(COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT(discord_id) DO UPDATE SET
                    {updates},
                    updated_at = CURRENT_TIMESTAMP
                """,
                (str(discord_id), *(values[column] for column in COLUMNS)),
            )

    @staticmethod
    def _serialize_json(value):
        return json.dumps(value) if value is not None else None

    @staticmethod
    def _deserialize_json(value):
        return json.loads(value) if value else None

    @staticmethod
    def serialize_token(token):
        return json.dumps(token)

    @staticmethod
    def deserialize_token(token_json):
        return json.loads(token_json) if token_json else None
