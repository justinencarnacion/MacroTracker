import unittest

from bot_messages import (
    add_totals,
    format_meal_logged,
    parse_macros,
    worksheet_title,
)

LIMITS = {"calories": 2050, "protein": 160, "carbs": 210, "fat": 70}


class WorksheetTitleTests(unittest.TestCase):
    def test_strips_characters_sheets_rejects(self):
        self.assertEqual(
            worksheet_title("Ju[st]in/:*?", "123456789"), "Justin (456789)"
        )

    def test_falls_back_when_name_is_empty(self):
        self.assertEqual(worksheet_title("[]", "42"), "Discord User (42)")


class ParseMacrosTests(unittest.TestCase):
    def test_missing_or_bad_values_become_zero(self):
        self.assertEqual(
            parse_macros({"calories": "150", "protein": None, "carbs": "x"}),
            {"calories": 150.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        )

    def test_add_totals(self):
        totals = {"calories": 500.0, "protein": 40.0, "carbs": 50.0, "fat": 10.0}
        meal = {"calories": 150.0, "protein": 35.0, "carbs": 0.0, "fat": 2.5}
        self.assertEqual(
            add_totals(totals, meal),
            {"calories": 650.0, "protein": 75.0, "carbs": 50.0, "fat": 12.5},
        )


class FormatMealLoggedTests(unittest.TestCase):
    def setUp(self):
        self.macros = {"calories": 300.0, "protein": 25.0, "carbs": 20.0, "fat": 12.5}

    def reply(self, totals, is_estimation=True):
        return format_meal_logged(
            "2 eggs and toast",
            self.macros,
            is_estimation,
            "Justin (456789)",
            totals,
            LIMITS,
        )

    def test_names_the_users_worksheet_tab(self):
        text = self.reply(dict(self.macros))
        self.assertIn("Logged to your Google Sheet tab [Justin (456789)]!", text)
        self.assertIn("(AI Estimated)", text)
        self.assertIn("**Calories:** 300 kcal | **P:** 25g | **C:** 20g | **F:** 12.5g", text)

    def test_manual_tag(self):
        self.assertIn("(Manual Input)", self.reply(dict(self.macros), False))

    def test_shows_daily_totals_and_remaining(self):
        totals = {"calories": 1800.0, "protein": 120.0, "carbs": 150.0, "fat": 50.0}
        text = self.reply(totals)
        self.assertIn("📊 **Today's Totals**", text)
        self.assertIn("**Calories (kcal):** 1800.0 / 2050 (Remaining: 250.0)", text)
        self.assertIn("**Protein (g):** 120.0 / 160 (Remaining: 40.0)", text)
        self.assertIn("**Carbs (g):** 150.0 / 210 (Remaining: 60.0)", text)
        self.assertIn("**Fat (g):** 50.0 / 70 (Remaining: 20.0)", text)

    def test_flags_exceeded_goals(self):
        totals = {"calories": 2200.0, "protein": 160.0, "carbs": 100.0, "fat": 80.5}
        text = self.reply(totals)
        self.assertIn("**Calories (kcal):** 2200.0 / 2050 (⚠️ EXCEEDED BY 150.0!)", text)
        self.assertIn("**Protein (g):** 160.0 / 160 (Remaining: 0.0)", text)
        self.assertIn("**Fat (g):** 80.5 / 70 (⚠️ EXCEEDED BY 10.5!)", text)


if __name__ == "__main__":
    unittest.main()
