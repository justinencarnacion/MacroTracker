import asyncio
import unittest
from datetime import date
from types import SimpleNamespace

from bot import embeds
from bot.replies import Reply
from bot.views.summary import TODAY_ID, WEEK_ID, SummaryView
from tracking.summaries import summarize_day, summarize_week

GOALS = {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70}


def meal(date_time, name="Eggs", calories=300, protein=20, carbs=10, fat=15):
    return {"date_time": date_time, "meal_name": name, "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


class EmbedTests(unittest.TestCase):
    def test_today_embed(self):
        embed = embeds.today_embed(summarize_day([meal("2026-10-14 08:05")], date(2026, 10, 14), GOALS))
        self.assertEqual(embed.title, "📅 Today · Wed, Oct 14")
        self.assertIn("1. `08:05` Eggs", embed.description)
        self.assertEqual([f.name for f in embed.fields], ["Calories", "Protein", "Carbs", "Fat"])
        self.assertIn("1,700 kcal left", embed.fields[0].value)
        self.assertEqual(embed.image.url, "attachment://today.png")

    def test_long_meal_lists_fit_embed_limits(self):
        meals = [meal(f"2026-10-14 {h:02d}:00", "A very long meal name " * 4) for h in range(24)]
        embed = embeds.today_embed(summarize_day(meals, date(2026, 10, 14), GOALS))
        self.assertLessEqual(len(embed.description), 4096)
        self.assertLessEqual(len(embed), 6000)

    def test_week_embed(self):
        embed = embeds.week_embed(summarize_week([meal("2026-10-12 12:00")], date(2026, 10, 14), GOALS))
        self.assertTrue(embed.title.startswith("📊 This week · Mon Oct 12"))
        self.assertIn("daily goals × 3 days", embed.description)
        self.assertEqual(embed.fields[-1].name, "Daily average")
        self.assertEqual(embed.image.url, "attachment://week.png")


class ReplyTests(unittest.TestCase):
    def test_text_reply_sends_only_content(self):
        self.assertEqual(Reply.of("hello").send_kwargs(lambda kind: None), {"content": "hello"})

    def test_card_reply_gets_fresh_file_and_view_each_time(self):
        reply = Reply(embed="EMBED", image=b"png-bytes", image_name="today.png", buttons="today")
        first = reply.send_kwargs(lambda kind: f"view:{kind}")
        second = reply.send_kwargs(lambda kind: f"view:{kind}")
        self.assertEqual(first["view"], "view:today")
        self.assertEqual(first["file"].filename, "today.png")
        self.assertIsNot(first["file"], second["file"])

    def test_edit_clears_old_card_for_text_replies(self):
        edit = Reply.of("Set your goals").edit_kwargs(lambda kind: None)
        self.assertEqual(edit, {"content": "Set your goals", "embed": None, "attachments": [], "view": None})


class SummaryViewTests(unittest.TestCase):
    def test_buttons_are_persistent_and_highlight_current_view(self):
        async def build():
            return SummaryView(SimpleNamespace(), current="week")
        view = asyncio.run(build())
        self.assertIsNone(view.timeout)
        self.assertTrue(view.is_persistent())
        buttons = {child.custom_id: child for child in view.children}
        self.assertEqual(set(buttons), {TODAY_ID, WEEK_ID})
        self.assertTrue(buttons[WEEK_ID].disabled)
        self.assertFalse(buttons[TODAY_ID].disabled)


if __name__ == "__main__":
    unittest.main()
