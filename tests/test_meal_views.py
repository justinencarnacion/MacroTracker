import asyncio
import unittest
from types import SimpleNamespace

from bot.views.meals import OPTION_LIMIT, ConfirmView, MealPicker, changes, meal_option


def meal(index=0, name="Chicken and rice", calories=980):
    return {"row_number": index + 2, "date_time": f"2026-10-15 12:{index % 60:02d}",
            "meal_name": name, "calories": calories, "protein": 56, "carbs": 121, "fat": 30}


class Interaction:
    def __init__(self, user_id):
        self.user = SimpleNamespace(id=user_id)
        self.sent = []
        self.response = SimpleNamespace(send_message=self._send)

    async def _send(self, content, ephemeral=False):
        self.sent.append((content, ephemeral))


class MealPickerTests(unittest.TestCase):
    def test_options_are_capped_and_fit_discord_limits(self):
        async def build():
            meals = [meal(i, "A very long meal name " * 10) for i in range(40)]
            return MealPicker(SimpleNamespace(), 1, "delete", meals)
        picker = asyncio.run(build())
        self.assertEqual(len(picker.select.options), OPTION_LIMIT)
        for option in picker.select.options:
            self.assertLessEqual(len(option.label), 100)
            self.assertLessEqual(len(option.description), 100)

    def test_option_label(self):
        option = meal_option(0, meal())
        self.assertEqual(option.label, "Thu Oct 15, 12:00 · Chicken and rice")
        self.assertEqual(option.description, "980 kcal · P 56g · C 121g · F 30g")

    def test_only_the_owner_can_use_it(self):
        async def check():
            picker = MealPicker(SimpleNamespace(), 1, "edit", [meal()])
            stranger, owner = Interaction(2), Interaction(1)
            return (await picker.interaction_check(stranger), stranger.sent,
                    await picker.interaction_check(owner))
        allowed_stranger, sent, allowed_owner = asyncio.run(check())
        self.assertFalse(allowed_stranger)
        self.assertTrue(sent and sent[0][1])  # told privately
        self.assertTrue(allowed_owner)


class ChangesTests(unittest.TestCase):
    def test_lists_only_changed_fields(self):
        before = meal()
        after = {"meal_name": "Chicken bowl", "calories": 900, "protein": 56, "carbs": 121, "fat": 30}
        self.assertEqual(changes(before, after),
                         ["Name: Chicken and rice → Chicken bowl", "Calories: 980 kcal → 900 kcal"])


class ConfirmViewTests(unittest.TestCase):
    def test_labels(self):
        async def build():
            import discord
            return ConfirmView(1, "Delete", discord.ButtonStyle.danger, None)
        view = asyncio.run(build())
        self.assertEqual([child.label for child in view.children], ["Delete", "Cancel"])


if __name__ == "__main__":
    unittest.main()
