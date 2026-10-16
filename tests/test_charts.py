import unittest
from datetime import date

from charts import theme
from charts.today import bar_color, bar_label, render_today
from charts.week import day_color, render_week
from tracking.summaries import summarize_day, summarize_week

GOALS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def meal(date_time, calories=0, protein=0, carbs=0, fat=0):
    return {"date_time": date_time, "meal_name": "Meal", "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


class ColorRuleTests(unittest.TestCase):
    def test_limits_turn_red_only_when_clearly_over(self):
        self.assertEqual(bar_color("calories", 1000, 2000), theme.BLURPLE)
        self.assertEqual(bar_color("calories", 2050, 2000), theme.GREEN)  # within 5%
        self.assertEqual(bar_color("calories", 2200, 2000), theme.RED)

    def test_protein_is_a_minimum(self):
        self.assertEqual(bar_color("protein", 100, 150), theme.BLURPLE)
        self.assertEqual(bar_color("protein", 300, 150), theme.GREEN)

    def test_bar_label_includes_percent(self):
        self.assertEqual(bar_label("calories", 980, 1900), "980 / 1,900 kcal · 52%")
        self.assertEqual(bar_label("fat", 30, 60), "30 / 60g · 50%")

    def test_week_day_colors(self):
        self.assertEqual(day_color(1500, 2000, is_today=True), theme.BLURPLE)
        self.assertEqual(day_color(1900, 2000, is_today=False), theme.GREEN)
        self.assertEqual(day_color(2500, 2000, is_today=False), theme.RED)


class RenderTests(unittest.TestCase):
    def test_today_png(self):
        png = render_today(summarize_day([meal("2026-10-14 08:00", 2500, 40, 90, 20)],
                                         date(2026, 10, 14), GOALS))
        self.assertTrue(png.startswith(PNG_SIGNATURE))
        self.assertLess(len(png), 500_000)

    def test_week_png_with_empty_and_future_days(self):
        png = render_week(summarize_week([meal("2026-10-12 12:00", 1800)],
                                         date(2026, 10, 14), GOALS))
        self.assertTrue(png.startswith(PNG_SIGNATURE))

    def test_renders_with_nothing_logged(self):
        self.assertTrue(render_today(summarize_day([], date(2026, 10, 14), GOALS)).startswith(PNG_SIGNATURE))
        self.assertTrue(render_week(summarize_week([], date(2026, 10, 12), GOALS)).startswith(PNG_SIGNATURE))


if __name__ == "__main__":
    unittest.main()
