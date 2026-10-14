import unittest
from datetime import datetime, timezone

import gspread

from tracking.service import TrackingService

GOALS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70}


def row(date_time, name, calories):
    return {"Date/Time": date_time, "Meal Name": name, "Calories (kcal)": calories,
            "Protein (g)": 0, "Carbs (g)": 0, "Fat (g)": 0}


class FakeSheet:
    def __init__(self, sheet_id, records):
        self.id = sheet_id
        self.records = records

    def get_all_records(self):
        return self.records


class FakeSpreadsheet:
    def __init__(self, sheets):
        self.sheets = sheets
        self.created = []

    def get_worksheet_by_id(self, sheet_id):
        for sheet in self.sheets.values():
            if sheet.id == sheet_id:
                return sheet
        raise gspread.exceptions.WorksheetNotFound(sheet_id)

    def worksheet(self, title):
        if title not in self.sheets:
            raise gspread.exceptions.WorksheetNotFound(title)
        return self.sheets[title]

    def add_worksheet(self, *args, **kwargs):
        self.created.append(args)
        raise AssertionError("read-only requests must not create tabs")


def user(timezone_name=None, worksheet_id=None, discord_id="111222333444555666"):
    return {"discord_id": discord_id, "display_name": "Alex", "worksheet_id": worksheet_id,
            "timezone": timezone_name, "goals": GOALS}


# 2026-10-15 03:30 UTC is still Wednesday 2026-10-14 in Los Angeles.
FIXED_UTC = datetime(2026, 10, 15, 3, 30, tzinfo=timezone.utc)


def clock(tz):
    return FIXED_UTC.astimezone(tz)


class TrackingServiceTests(unittest.TestCase):
    def setUp(self):
        self.sheet = FakeSheet(7, [
            row("2026-10-12 12:00", "Monday lunch", 600),
            row("2026-10-14 08:00", "Wednesday breakfast", 400),
            row("2026-10-15 01:00", "Thursday early", 300),
        ])
        self.spreadsheet = FakeSpreadsheet({"Alex (555666)": self.sheet})
        self.service = TrackingService(self.spreadsheet, "America/Los_Angeles", clock=clock)

    def test_today_uses_the_users_timezone(self):
        self.assertEqual(str(self.service.today_for(user())), "2026-10-14")
        self.assertEqual(str(self.service.today_for(user("Europe/London"))), "2026-10-15")

    def test_day_summary_reads_only_today(self):
        summary = self.service.day_summary(user(worksheet_id=7), GOALS)
        self.assertEqual([m["meal_name"] for m in summary.meals], ["Wednesday breakfast"])

    def test_week_summary_monday_through_today(self):
        summary = self.service.week_summary(user(), GOALS)
        self.assertEqual(summary.totals["calories"], 1000)  # Thursday is in the future in LA
        self.assertEqual(summary.days_elapsed, 3)

    def test_user_without_a_tab_gets_empty_summary_and_no_tab_is_created(self):
        summary = self.service.day_summary(user(discord_id="999999999999000000"), GOALS)
        self.assertEqual(summary.meals, [])
        self.assertEqual(self.spreadsheet.created, [])


if __name__ == "__main__":
    unittest.main()
