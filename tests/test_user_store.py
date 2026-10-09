import sqlite3
import tempfile
import unittest
from pathlib import Path

from user_store import UserStore


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "users.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_ensure_user_creates_and_renames(self):
        store = UserStore(self.path)
        self.assertEqual(store.ensure_user("1", "Alex")["display_name"], "Alex")
        store.set_worksheet_id("1", 42)
        user = store.ensure_user("1", "Alexander")
        self.assertEqual(user["display_name"], "Alexander")
        self.assertEqual(user["worksheet_id"], 42)

    def test_fields_persist_independently(self):
        store = UserStore(self.path)
        store.ensure_user("1", "Alex")
        store.set_goals("1", {"calories": 2000})
        store.set_timezone("1", "America/New_York")
        user = store.get("1")
        self.assertEqual(user["goals"], {"calories": 2000})
        self.assertEqual(user["timezone"], "America/New_York")

    def test_migrates_old_schema_without_worksheet_id(self):
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE users (discord_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,"
                " token_json TEXT, spreadsheet_id TEXT, tab_mode TEXT NOT NULL DEFAULT 'monthly',"
                " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute("INSERT INTO users (discord_id, display_name) VALUES ('1', 'Old')")
        store = UserStore(self.path)
        self.assertIsNone(store.get("1")["worksheet_id"])
        store.set_worksheet_id("1", 7)
        self.assertEqual(store.get("1")["worksheet_id"], 7)


if __name__ == "__main__":
    unittest.main()
