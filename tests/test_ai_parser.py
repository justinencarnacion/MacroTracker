import asyncio
import json
import unittest
from types import SimpleNamespace

from google.genai import errors as genai_errors

from bot.ai_parser import ParseError, parse_input_with_ai, validate_ai_response


class FakeModels:
    """Fails with the given status code for listed models, succeeds otherwise."""

    def __init__(self, failures):
        self.failures = failures
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append(model)
        if model in self.failures:
            code = self.failures[model]
            error_class = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
            raise error_class(code, {"error": {"code": code, "message": "x", "status": "x"}})
        return SimpleNamespace(text=json.dumps({"intent": "LOG_MEAL", "calories": 100}))


def fake_client(failures):
    models = FakeModels(failures)
    return SimpleNamespace(aio=SimpleNamespace(models=models)), models


def parse(**data):
    return validate_ai_response(json.dumps(data))


class ValidateAiResponseTests(unittest.TestCase):
    def test_log_meal_coerces_numbers_and_fills_missing_macros(self):
        parsed = parse(intent="LOG_MEAL", meal_name="Eggs", calories="150", protein=12.0, carbs=None)
        self.assertEqual(parsed.intent, "LOG_MEAL")
        self.assertEqual(parsed.macros, {"calories": 150, "protein": 12, "carbs": 0, "fat": 0})

    def test_log_meal_without_any_macros_is_rejected(self):
        with self.assertRaises(ParseError):
            parse(intent="LOG_MEAL", meal_name="hi", calories=0)

    def test_out_of_range_values_are_rejected(self):
        with self.assertRaises(ParseError):
            parse(intent="LOG_MEAL", calories=50000)
        with self.assertRaises(ParseError):
            parse(intent="LOG_MEAL", calories=-5)
        with self.assertRaises(ParseError):
            parse(intent="LOG_MEAL", calories="lots")

    def test_update_goals_keeps_only_provided_values(self):
        parsed = parse(intent="UPDATE_GOALS", calories=2200, protein=None, carbs=None, fat=70)
        self.assertEqual(parsed.macros, {"calories": 2200, "fat": 70})

    def test_update_goals_with_no_values_is_rejected(self):
        with self.assertRaises(ParseError):
            parse(intent="UPDATE_GOALS", calories=None)

    def test_set_timezone_validates_iana_names(self):
        self.assertEqual(parse(intent="SET_TIMEZONE", timezone="America/New_York").timezone, "America/New_York")
        with self.assertRaises(ParseError):
            parse(intent="SET_TIMEZONE", timezone="Mars/Olympus")

    def test_unknown_intent_and_bad_json(self):
        self.assertEqual(parse(intent="CHITCHAT").intent, "OTHER")
        with self.assertRaises(ParseError):
            validate_ai_response("not json")
        with self.assertRaises(ParseError):
            validate_ai_response("[1, 2]")


class ModelFallbackTests(unittest.TestCase):
    def test_falls_back_when_model_is_overloaded_or_rate_limited(self):
        client, models = fake_client({"a": 503, "b": 429})
        parsed = asyncio.run(parse_input_with_ai(client, ["a", "b", "c"], "toast"))
        self.assertEqual(parsed.macros["calories"], 100)
        self.assertEqual(models.calls, ["a", "b", "c"])

    def test_other_client_errors_do_not_fall_back(self):
        client, models = fake_client({"a": 404})
        with self.assertRaises(genai_errors.ClientError):
            asyncio.run(parse_input_with_ai(client, ["a", "b"], "toast"))
        self.assertEqual(models.calls, ["a"])

    def test_raises_when_every_model_is_overloaded(self):
        client, _ = fake_client({"a": 503, "b": 503})
        with self.assertRaises(genai_errors.ServerError):
            asyncio.run(parse_input_with_ai(client, ["a", "b"], "toast"))


if __name__ == "__main__":
    unittest.main()
