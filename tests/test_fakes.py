"""Keep the simulated-testing fakes faithful to the real services they replace."""

import asyncio
import time
import unittest

import discord
from gspread.exceptions import APIError

from bot.ai_parser import parse_input_with_ai
from sheets.sheet_manager import (
    delete_meal,
    find_worksheet_for_user,
    get_meals,
    get_or_create_worksheet,
    update_meal,
)
from testing.fakes import discord_api
from testing.fakes.discord_api import FakeInteraction, FakeUser
from testing.fakes.gemini import FakeGemini
from testing.fakes.spreadsheet import FakeSpreadsheet
from testing.harness import MODELS, Harness


class FakeSpreadsheetTests(unittest.TestCase):
    def test_works_with_the_real_sheet_helpers(self):
        spreadsheet = FakeSpreadsheet()
        self.assertIsNone(find_worksheet_for_user(spreadsheet, None, "Alice"))
        sheet = get_or_create_worksheet(spreadsheet, "Alice")
        sheet.append_row(["2026-10-29 08:00", "Eggs", 150, 12, 1, 10])
        sheet.append_row(["2026-10-29 12:00", "Rice", 205, 4, 45, 0])

        update_meal(sheet, 2, "Three eggs", 230, 18, 2, 15)
        delete_meal(sheet, 3)

        meals = get_meals(sheet)
        self.assertEqual([(m["meal_name"], m["calories"]) for m in meals], [("Three eggs", 230)])
        self.assertEqual(meals[0]["date_time"], "2026-10-29 08:00")
        self.assertIs(find_worksheet_for_user(spreadsheet, sheet.id, "renamed"), sheet)

    def test_injected_failures_raise_gspread_errors_then_recover(self):
        spreadsheet = FakeSpreadsheet()
        spreadsheet.fail_next(code=429)
        with self.assertRaises(APIError) as caught:
            spreadsheet.worksheets()
        self.assertEqual(caught.exception.code, 429)
        self.assertEqual(spreadsheet.worksheets(), [])


class FakeGeminiTests(unittest.TestCase):
    def parse(self, gemini, text):
        return asyncio.run(parse_input_with_ai(gemini, MODELS, text))

    def test_answers_pass_the_real_validator(self):
        gemini = FakeGemini()
        exact = self.parse(gemini, "450 cals, 35p, 40c, 12f")
        self.assertEqual((exact.intent, exact.is_estimation), ("LOG_MEAL", False))
        self.assertEqual(exact.macros, {"calories": 450, "protein": 35, "carbs": 40, "fat": 12})
        estimate = self.parse(gemini, "2 eggs and toast")
        self.assertTrue(estimate.is_estimation)
        self.assertEqual(estimate.macros["calories"], 2 * 78 + 80)
        self.assertEqual(self.parse(gemini, "set my goals to 2200 cals, 180p").macros,
                         {"calories": 2200, "protein": 180})
        self.assertEqual(self.parse(gemini, "set my timezone to London").timezone, "Europe/London")
        self.assertEqual(self.parse(gemini, "how's my week?").intent, "SHOW_WEEK")
        self.assertEqual(self.parse(gemini, "hello").intent, "OTHER")

    def test_outage_triggers_the_bots_model_fallback(self):
        gemini = FakeGemini()
        gemini.outage(503, model=MODELS[0])
        self.parse(gemini, "banana")
        self.assertEqual(gemini.outcomes[(MODELS[0], 503)], 1)
        self.assertEqual(gemini.outcomes[(MODELS[1], "ok")], 1)

    def test_daily_quota_answers_429_like_the_free_tier(self):
        gemini = FakeGemini(daily_quota=1)
        self.parse(gemini, "banana")
        self.parse(gemini, "banana")  # first model is out of quota; the next answers
        self.assertEqual(gemini.outcomes[(MODELS[0], 429)], 1)


class FakeInteractionTests(unittest.TestCase):
    def test_enforces_discords_response_rules(self):
        async def scenario():
            interaction = FakeInteraction(FakeUser(1, "Alice"))
            with self.assertRaises(discord.NotFound):
                await interaction.followup.send("too early")
            await interaction.response.defer()
            with self.assertRaises(discord.InteractionResponded):
                await interaction.response.send_message("twice")
            await interaction.followup.send("fine")

        asyncio.run(scenario())

    def test_expires_after_three_seconds(self):
        async def scenario():
            interaction = FakeInteraction(FakeUser(1, "Alice"))
            interaction.created = time.monotonic() - discord_api.INTERACTION_DEADLINE - 1
            with self.assertRaises(discord.NotFound):
                await interaction.response.defer()

        asyncio.run(scenario())


class HarnessSmokeTests(unittest.TestCase):
    def test_member_logs_a_meal_and_sees_today(self):
        async def scenario():
            async with Harness() as harness:
                alice = harness.user("Alice")
                await alice.dm("set my goals to 2200 cals, 180p, 220c, 70f")
                logged = await alice.dm("2 eggs and toast")
                card = await alice.slash("today")
                outsider = await harness.user("Eve", member=False).dm("2 eggs")
                return logged, card, outsider

        logged, card, outsider = asyncio.run(scenario())
        self.assertIn("Logged!", logged.text)
        self.assertTrue(card.image)
        self.assertIn("2 Eggs And Toast", card.text)
        self.assertEqual(card.labels(), ["Today", "Week"])
        self.assertIn("only available to members", outsider.text)
