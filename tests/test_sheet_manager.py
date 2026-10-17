import unittest

import gspread

from sheets.sheet_manager import (
    find_worksheet_for_user,
    get_meals,
    get_worksheet_for_user,
    update_meal,
    worksheet_title,
)


class FakeSheet:
    def __init__(self, sheet_id=1, records=None):
        self.id = sheet_id
        self.records = records or []
        self.updates = []
        self.deleted = []

    def row_values(self, row):
        return ["Date/Time"]

    def get_all_records(self):
        return self.records

    def update(self, values=None, range_name=None):
        self.updates.append((range_name, values))

    def delete_rows(self, row_number):
        self.deleted.append(row_number)


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

    def add_worksheet(self, title, rows, cols):
        sheet = FakeSheet(sheet_id=100 + len(self.created))
        self.sheets[title] = sheet
        self.created.append(title)
        return sheet


class GetWorksheetForUserTests(unittest.TestCase):
    def test_finds_by_id_even_after_rename(self):
        sheet = FakeSheet(sheet_id=5)
        spreadsheet = FakeSpreadsheet({"Old Name (123456)": sheet})
        self.assertIs(get_worksheet_for_user(spreadsheet, 5, "New Name (123456)"), sheet)
        self.assertEqual(spreadsheet.created, [])

    def test_falls_back_to_title_then_creates(self):
        sheet = FakeSheet(sheet_id=5)
        spreadsheet = FakeSpreadsheet({"Alex (123456)": sheet})
        self.assertIs(get_worksheet_for_user(spreadsheet, None, "Alex (123456)"), sheet)
        get_worksheet_for_user(spreadsheet, 999, "Sam (654321)")
        self.assertEqual(spreadsheet.created, ["Sam (654321)"])


class FindWorksheetTests(unittest.TestCase):
    def test_finds_by_id_or_title_without_creating(self):
        sheet = FakeSheet(sheet_id=5)
        spreadsheet = FakeSpreadsheet({"Alex (123456)": sheet})
        self.assertIs(find_worksheet_for_user(spreadsheet, 5, "Renamed (123456)"), sheet)
        self.assertIs(find_worksheet_for_user(spreadsheet, None, "Alex (123456)"), sheet)
        self.assertIsNone(find_worksheet_for_user(spreadsheet, 999, "Sam (654321)"))
        self.assertEqual(spreadsheet.created, [])


class WorksheetTitleTests(unittest.TestCase):
    def test_strips_forbidden_characters_and_adds_id_suffix(self):
        self.assertEqual(worksheet_title("A/B:C?", "111222333444123456"), "ABC (123456)")
        self.assertEqual(worksheet_title("  ", "111222333444123456"), "Discord User (123456)")


class MealTests(unittest.TestCase):
    def test_get_meals_skips_marker_rows_and_filters_dates(self):
        sheet = FakeSheet(records=[
            {"Date/Time": "2026-10-01 08:00", "Meal Name": "Eggs", "Calories (kcal)": 150, "Protein (g)": 12, "Carbs (g)": 1, "Fat (g)": 10},
            {"Date/Time": "2026-10-01 TOTAL", "Meal Name": "Logged", "Calories (kcal)": 150},
            {"Date/Time": "--- 2026-10-02 ---", "Meal Name": "---"},
            {"Date/Time": "2026-10-02 12:00", "Meal Name": "Rice", "Calories (kcal)": "", "Protein (g)": 4, "Carbs (g)": 45, "Fat (g)": 0},
        ])
        meals = get_meals(sheet, "2026-10-02", "2026-10-02")
        self.assertEqual([meal["meal_name"] for meal in meals], ["Rice"])
        self.assertEqual(meals[0]["row_number"], 5)
        self.assertEqual(meals[0]["calories"], 0.0)

    def test_update_meal_keeps_timestamp_column(self):
        sheet = FakeSheet()
        update_meal(sheet, 3, "Toast", 100, 3, 18, 1)
        self.assertEqual(sheet.updates, [("B3:F3", [["Toast", 100, 3, 18, 1]])])


if __name__ == "__main__":
    unittest.main()
