import io
import unittest
from contextlib import redirect_stdout

from display import display_dashboard

LIMITS = {"calories": 2050, "protein": 160, "carbs": 210, "fat": 70}


class DisplayDashboardTests(unittest.TestCase):
    def test_cli_dashboard_output_is_unchanged(self):
        totals = {"calories": 2100.0, "protein": 100.0, "carbs": 0.0, "fat": 70.0}
        out = io.StringIO()
        with redirect_stdout(out):
            display_dashboard(totals, LIMITS, "justin")
        lines = out.getvalue().splitlines()
        self.assertIn("    CURRENT DAILY MACRO STATUS [JUSTIN]    ", lines)
        self.assertIn("Calories (kcal) : 2100.0 / 2050 (⚠️ EXCEEDED BY 50.0!)", lines)
        self.assertIn("Protein (g)     : 100.0 / 160 (Remaining: 60.0)", lines)
        self.assertIn("Carbs (g)       : 0.0 / 210 (Remaining: 210.0)", lines)
        self.assertIn("Fat (g)         : 70.0 / 70 (Remaining: 0.0)", lines)


if __name__ == "__main__":
    unittest.main()
