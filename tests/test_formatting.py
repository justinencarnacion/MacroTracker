import re
import unittest
from datetime import date

from bot import formatting
from tracking.summaries import summarize_day, summarize_week

GOALS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70}


def meal(date_time, name="Meal", calories=0, protein=0, carbs=0, fat=0):
    return {"date_time": date_time, "meal_name": name, "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


class HelperTests(unittest.TestCase):
    def test_amount(self):
        self.assertEqual(formatting.amount(1640.0), "1,640")
        self.assertEqual(formatting.amount(12.5), "12.5")
        self.assertEqual(formatting.amount(12.04), "12")

    def test_progress_bar_is_capped(self):
        self.assertEqual(formatting.progress_bar(50, 100, width=10), "█████░░░░░")
        self.assertEqual(formatting.progress_bar(500, 100, width=10), "█" * 10)
        self.assertEqual(formatting.progress_bar(10, 0, width=4), "░░░░")

    def test_left_today_marks_overages(self):
        line = formatting.format_left_today(
            {"calories": 410, "protein": 64, "carbs": -15, "fat": 0}
        )
        self.assertEqual(line, "📉 **Left today:** 410 kcal · P 64g · C 15g over · F 0g")


class DayFormatTests(unittest.TestCase):
    def test_numbered_meals_and_progress(self):
        summary = summarize_day(
            [meal("2026-10-14 08:05", "Eggs and toast", 220, 15, 16, 11)],
            date(2026, 10, 14), GOALS,
        )
        text = formatting.format_day(summary)
        self.assertIn("Today · Wed, Oct 14", text)
        self.assertIn("1. `08:05` Eggs and toast — 220 kcal · P 15g · C 16g · F 11g", text)
        self.assertIn("1,780 kcal left", text)

    def test_empty_day(self):
        text = formatting.format_day(summarize_day([], date(2026, 10, 14), GOALS))
        self.assertIn("Nothing logged yet today.", text)

    def test_long_lists_are_truncated_and_fit_discord(self):
        meals = [meal(f"2026-10-14 {h:02d}:{m:02d}", "A very descriptive meal name " * 2, 100)
                 for h in range(10) for m in range(0, 60, 15)]
        text = formatting.format_day(summarize_day(meals, date(2026, 10, 14), GOALS))
        listed = len(re.findall(r"^\d+\. ", text, flags=re.MULTILINE))
        self.assertLessEqual(listed, formatting.MAX_LISTED_MEALS)
        self.assertIn(f"…and {len(meals) - listed} more", text)
        self.assertIn("**Progress**", text)  # never cut off by long meal lists
        self.assertIn("4,000 / 2,000", text)
        self.assertLessEqual(len(text), formatting.DISCORD_LIMIT)


class WeekFormatTests(unittest.TestCase):
    def test_week_table_and_pace(self):
        summary = summarize_week(
            [meal("2026-10-12 12:00", calories=1800, protein=140)],
            date(2026, 10, 14), GOALS,
        )
        text = formatting.format_week(summary)
        self.assertIn("Mon Oct 12 – Sun Oct 18** (day 3 of 7)", text)
        self.assertIn("daily goals × 3 days", text)
        self.assertRegex(text, r"Tue 13\s+—")
        self.assertRegex(text, r"Thu 15\s+·")
        self.assertIn("4,200 kcal left", text)


class GoalsFormatTests(unittest.TestCase):
    def test_goals(self):
        text = formatting.format_goals(GOALS)
        self.assertIn("**Calories:** 2,000 kcal", text)
        self.assertIn("**Protein:** 150g", text)
        self.assertTrue(formatting.format_goals_updated(GOALS).startswith("✅ **Goals updated!**\n• "))


if __name__ == "__main__":
    unittest.main()
