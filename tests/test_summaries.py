import unittest
from datetime import date

from tracking.summaries import summarize_day, summarize_week, week_bounds

GOALS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70}


def meal(date_time, name="Meal", calories=0, protein=0, carbs=0, fat=0):
    return {"date_time": date_time, "meal_name": name, "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


class WeekBoundsTests(unittest.TestCase):
    def test_monday_to_sunday(self):
        # 2026-10-14 is a Wednesday.
        self.assertEqual(week_bounds(date(2026, 10, 14)), (date(2026, 10, 12), date(2026, 10, 18)))

    def test_sunday_belongs_to_the_week_that_started_monday(self):
        self.assertEqual(week_bounds(date(2026, 10, 18))[0], date(2026, 10, 12))

    def test_monday_starts_its_own_week(self):
        self.assertEqual(week_bounds(date(2026, 10, 12))[0], date(2026, 10, 12))


class DaySummaryTests(unittest.TestCase):
    def test_orders_meals_and_computes_remaining(self):
        meals = [
            meal("2026-10-14 18:30", "Dinner", 800, 60, 70, 30),
            meal("2026-10-14 08:00", "Breakfast", 400, 30, 40, 15),
            meal("2026-10-13 12:00", "Yesterday", 999, 99, 99, 99),
        ]
        summary = summarize_day(meals, date(2026, 10, 14), GOALS)
        self.assertEqual([m["meal_name"] for m in summary.meals], ["Breakfast", "Dinner"])
        self.assertEqual(summary.totals["calories"], 1200)
        self.assertEqual(summary.remaining, {"calories": 800, "protein": 60, "carbs": 90, "fat": 25})

    def test_over_goal_is_negative(self):
        summary = summarize_day([meal("2026-10-14 12:00", calories=2300)], date(2026, 10, 14), GOALS)
        self.assertEqual(summary.remaining["calories"], -300)

    def test_skips_unreadable_timestamps(self):
        summary = summarize_day([meal("not a date", calories=500)], date(2026, 10, 14), GOALS)
        self.assertEqual(summary.meals, [])


class WeekSummaryTests(unittest.TestCase):
    def setUp(self):
        self.meals = [
            meal("2026-10-12 12:00", calories=1800, protein=140),  # Monday
            meal("2026-10-14 12:00", calories=2100, protein=150),  # Wednesday (today)
            meal("2026-10-11 12:00", calories=5000),  # previous Sunday: excluded
        ]
        self.summary = summarize_week(self.meals, date(2026, 10, 14), GOALS)

    def test_week_runs_monday_to_sunday(self):
        self.assertEqual([d.day.day for d in self.summary.days], [12, 13, 14, 15, 16, 17, 18])

    def test_target_is_goal_times_days_so_far(self):
        self.assertEqual(self.summary.days_elapsed, 3)
        self.assertEqual(self.summary.target["calories"], 6000)
        self.assertEqual(self.summary.totals["calories"], 3900)
        self.assertEqual(self.summary.remaining["calories"], 2100)

    def test_empty_and_future_days(self):
        tuesday, thursday = self.summary.days[1], self.summary.days[3]
        self.assertEqual(tuesday.meal_count, 0)
        self.assertFalse(tuesday.is_future)
        self.assertTrue(thursday.is_future)

    def test_daily_average_counts_empty_days(self):
        self.assertEqual(self.summary.daily_average["calories"], 1300)


if __name__ == "__main__":
    unittest.main()
