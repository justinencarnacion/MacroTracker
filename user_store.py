import json
import sqlite3
from pathlib import Path


DEFAULT_DATABASE = Path("storage") / "user_data.db"


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
                    tab_mode TEXT NOT NULL DEFAULT 'monthly',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, discord_id):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT discord_id, display_name, token_json, spreadsheet_id, tab_mode
                FROM users WHERE discord_id = ?
                """,
                (str(discord_id),),
            ).fetchone()
        if row is None:
            return None
        return {
            "discord_id": row[0],
            "display_name": row[1],
            "token_json": row[2],
            "spreadsheet_id": row[3],
            "tab_mode": row[4],
        }

    def upsert_token(self, discord_id, display_name, token_json):
        self._upsert(discord_id, display_name, token_json=token_json)

    def set_spreadsheet(self, discord_id, spreadsheet_id):
        self._upsert(discord_id, spreadsheet_id=spreadsheet_id)

    def set_tab_mode(self, discord_id, tab_mode):
        self._upsert(discord_id, tab_mode=tab_mode)

    def _upsert(self, discord_id, display_name=None, **fields):
        existing = self.get(discord_id)
        if existing is None:
            values = {
                "display_name": display_name or str(discord_id),
                "token_json": None,
                "spreadsheet_id": None,
                "tab_mode": "monthly",
            }
        else:
            values = existing
        values.update({key: value for key, value in fields.items() if value is not None})
        if display_name is not None:
            values["display_name"] = display_name

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users
                    (discord_id, display_name, token_json, spreadsheet_id, tab_mode)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    token_json = excluded.token_json,
                    spreadsheet_id = excluded.spreadsheet_id,
                    tab_mode = excluded.tab_mode,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    str(discord_id),
                    values["display_name"],
                    values["token_json"],
                    values["spreadsheet_id"],
                    values["tab_mode"],
                ),
            )

    @staticmethod
    def serialize_token(token):
        return json.dumps(token)

    @staticmethod
    def deserialize_token(token_json):
        return json.loads(token_json) if token_json else None
