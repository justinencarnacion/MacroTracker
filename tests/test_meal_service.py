import unittest
from datetime import date

import gspread

from tracking.meal_service import InvalidMeal, MealChanged, MealRef, MealService, parse_meal_edit


def record(date_time, name, calories, protein=0, carbs=0, fat=0):
    return {"Date/Time": date_time, "Meal Name": name, "Calories (kcal)": calories,
            "Protein (g)": protein, "Carbs (g)": carbs, "Fat (g)": fat}


class FakeSheet:
    def __init__(self, records):
        self.id = 7
        self.records = list(records)
        self.updates = []
        self.deleted = []

    def get_all_records(self):
        return self.records

    def update(self, values=None, range_name=None):
        self.updates.append((range_name, values))

    def delete_rows(self, row_number):
        self.deleted.append(row_number)
        del self.records[row_number - 2]


class FakeSpreadsheet:
    def __init__(self, sheet):
        self.sheet = sheet

    def get_worksheet_by_id(self, sheet_id):
        if sheet_id == self.sheet.id:
            return self.sheet
        raise gspread.exceptions.WorksheetNotFound(sheet_id)

    def worksheet(self, title):
        raise gspread.exceptions.WorksheetNotFound(title)


class FakeTracking:
    def __init__(self, sheet, today):
        self.sheet, self.today = sheet, today

    def today_for(self, user):
        return self.today

    def meals_between(self, user, start, end):
        from sheets.sheet_manager import get_meals
        return get_meals(self.sheet, start, end)


USER = {"discord_id": "111222333444555666", "display_name": "Alex", "worksheet_id": 7}


def service(records, today=date(2026, 10, 15)):
    sheet = FakeSheet(records)
    return MealService(FakeSpreadsheet(sheet), FakeTracking(sheet, today)), sheet


class RecentMealsTests(unittest.TestCase):
    def test_last_seven_days_newest_first(self):
        svc, _ = service([
            record("2026-10-08 12:00", "Too old", 500),
            record("2026-10-09 09:00", "Oldest allowed", 300),
            record("2026-10-15 08:00", "Breakfast", 400),
            record("2026-10-14 19:00", "Dinner", 800),
        ])
        self.assertEqual([m["meal_name"] for m in svc.recent_meals(USER)],
                         ["Breakfast", "Dinner", "Oldest allowed"])


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.svc, self.sheet = service([
            record("2026-10-15 08:00", "Eggs", 220, 15, 2, 15),       # row 2
            record("2026-10-15 12:00", "Chicken", 650, 55, 60, 20),   # row 3
            record("2026-10-15 18:00", "Ice cream", 1020, 15, 114, 57),  # row 4
        ])
        meals = self.svc.recent_meals(USER)
        self.refs = {m["meal_name"]: MealRef.from_meal(m) for m in meals}

    def test_delete_the_picked_row(self):
        self.svc.delete(USER, self.refs["Ice cream"])
        self.assertEqual(self.sheet.deleted, [4])

    def test_finds_a_meal_that_moved(self):
        self.svc.delete(USER, self.refs["Eggs"])  # row 2 removed; Ice cream shifts to row 3
        self.svc.delete(USER, self.refs["Ice cream"])
        self.assertEqual(self.sheet.deleted, [2, 3])

    def test_refuses_when_the_meal_was_changed(self):
        self.sheet.records[2] = record("2026-10-15 18:00", "Ice cream", 500, 15, 114, 57)
        with self.assertRaises(MealChanged):
            self.svc.delete(USER, self.refs["Ice cream"])
        self.assertEqual(self.sheet.deleted, [])

    def test_refuses_ambiguous_duplicates_after_a_shift(self):
        self.sheet.records = [record("2026-10-15 08:00", "Eggs", 220, 15, 2, 15)] * 3
        ref = MealRef(row_number=9, date_time="2026-10-15 08:00", meal_name="Eggs",
                      calories=220, protein=15, carbs=2, fat=15)
        with self.assertRaises(MealChanged):
            self.svc.delete(USER, ref)

    def test_update_keeps_timestamp_and_writes_new_values(self):
        values = parse_meal_edit("Chicken bowl", {"calories": "600", "protein": "50",
                                                  "carbs": "55", "fat": "18"})
        self.svc.update(USER, self.refs["Chicken"], values)
        self.assertEqual(self.sheet.updates, [("B3:F3", [["Chicken bowl", 600, 50, 55, 18]])])


class ParseMealEditTests(unittest.TestCase):
    def test_cleans_numbers(self):
        self.assertEqual(
            parse_meal_edit("  Toast ", {"calories": "1,200", "protein": "4.5", "carbs": "", "fat": "1"}),
            {"meal_name": "Toast", "calories": 1200, "protein": 4.5, "carbs": 0, "fat": 1})

    def test_rejects_bad_input(self):
        for name, values in (
            ("", {"calories": "100"}),
            ("Toast", {"calories": "lots"}),
            ("Toast", {"calories": "-5"}),
            ("Toast", {"calories": "99999"}),
            ("Toast", {"calories": "0", "protein": "0"}),
        ):
            with self.assertRaises(InvalidMeal):
                parse_meal_edit(name, values)


if __name__ == "__main__":
    unittest.main()
