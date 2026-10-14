import unittest

from tracking.goals import GoalsIncomplete, has_goals, merge_goals

FULL = {"calories": 2200, "protein": 180, "carbs": 220, "fat": 70}


class GoalsTests(unittest.TestCase):
    def test_has_goals_requires_all_four(self):
        self.assertFalse(has_goals(None))
        self.assertFalse(has_goals({}))
        self.assertFalse(has_goals({"calories": 2000}))
        self.assertTrue(has_goals(FULL))

    def test_first_time_requires_all_four(self):
        with self.assertRaises(GoalsIncomplete) as caught:
            merge_goals(None, {"calories": 2200, "protein": 180})
        self.assertEqual(caught.exception.missing, ("carbs", "fat"))
        self.assertIn("carbs, fat", str(caught.exception))

    def test_first_time_with_all_four(self):
        self.assertEqual(merge_goals(None, FULL), FULL)

    def test_later_updates_can_be_partial(self):
        updated = merge_goals(FULL, {"calories": 2000, "fat": None})
        self.assertEqual(updated, {**FULL, "calories": 2000})

    def test_ignores_unknown_keys(self):
        self.assertEqual(merge_goals(FULL, {"fiber": 30}), FULL)


if __name__ == "__main__":
    unittest.main()
