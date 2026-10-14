import json
import logging
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from google.genai import errors as genai_errors
from google.genai import types

from core.macros import GOAL_LIMITS, MACRO_KEYS, MEAL_LIMITS

logger = logging.getLogger(__name__)

SUMMARY_INTENTS = ("SHOW_TODAY", "SHOW_WEEK", "SHOW_GOALS")

SYSTEM_PROMPT = """
You are an expert nutrition assistant. Analyze the user's message.
Determine if they want to:
1. "LOG_MEAL": Log food or manual macros (e.g. "2 eggs and toast" or "150 cals, 35p").
2. "UPDATE_GOALS": Update their daily goal limits (e.g. "change my goals to 2200 cals, 180p, 200c, 70f").
3. "SET_TIMEZONE": Set their timezone (e.g. "I'm in New York", "set my timezone to PST").
4. "SHOW_TODAY": See what they ate today or what they have left today
   (e.g. "what did I eat today?", "how many macros do I have left?").
5. "SHOW_WEEK": See their progress this week (e.g. "how's my week going?", "weekly summary").
6. "SHOW_GOALS": See their current goals (e.g. "what are my goals?").
7. "OTHER": Anything else (greetings, questions, unclear messages).

Return a JSON object with this EXACT structure:
{
  "intent": "LOG_MEAL" | "UPDATE_GOALS" | "SET_TIMEZONE" | "SHOW_TODAY" | "SHOW_WEEK" | "SHOW_GOALS" | "OTHER",
  "meal_name": "Short descriptive title" (LOG_MEAL only),
  "calories": number or null,
  "protein": number or null,
  "carbs": number or null,
  "fat": number or null,
  "is_estimation": boolean (true if estimated food, false if exact manual inputs),
  "timezone": "IANA timezone name such as America/New_York" (SET_TIMEZONE only)
}
For LOG_MEAL, always fill in all four macros. If the user describes food
without numbers, estimate them from typical portion sizes and set
"is_estimation" to true. If they give numbers, use them exactly, set any
macro they left out to null, and set "is_estimation" to false.
For UPDATE_GOALS, set any goal the user did not mention to null.
For SET_TIMEZONE, SHOW_TODAY, SHOW_WEEK, SHOW_GOALS, and OTHER, set the macros to null.
"""


class ParseError(ValueError):
    """The AI response could not be turned into a safe action."""


@dataclass
class ParsedMessage:
    intent: str
    meal_name: str = "Meal"
    macros: dict = field(default_factory=dict)
    is_estimation: bool = False
    timezone: str | None = None


GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    response_mime_type="application/json",
    temperature=0.1,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


def is_overloaded(error):
    """True for errors where another model may succeed (5xx or rate limit)."""
    return isinstance(error, genai_errors.ServerError) or (
        isinstance(error, genai_errors.ClientError) and error.code == 429
    )


async def parse_input_with_ai(client, models, user_text):
    """Try each model in order, moving on when one is overloaded."""
    if isinstance(models, str):
        models = [models]
    for index, model in enumerate(models):
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=user_text, config=GENERATION_CONFIG
            )
        except genai_errors.APIError as error:
            if not is_overloaded(error) or index == len(models) - 1:
                raise
            logger.warning("Gemini model %s unavailable (%s); trying %s",
                           model, error.code, models[index + 1])
            continue
        return validate_ai_response(response.text)


def _to_number(value, name, upper_bound):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ParseError(f"{name} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ParseError(f"{name} must be a number.") from error
    if number < 0 or number > upper_bound:
        raise ParseError(f"{name} value {number:g} looks wrong.")
    return int(number) if number.is_integer() else round(number, 1)


def validate_ai_response(raw_text):
    try:
        data = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise ParseError("The AI response was not valid JSON.") from error
    if not isinstance(data, dict):
        raise ParseError("The AI response was not a JSON object.")

    intent = str(data.get("intent", "OTHER")).upper()

    if intent == "LOG_MEAL":
        macros = {
            key: _to_number(data.get(key), key, MEAL_LIMITS[key]) or 0
            for key in MACRO_KEYS
        }
        if not any(macros.values()):
            raise ParseError("I couldn't find any calories or macros in that meal.")
        meal_name = str(data.get("meal_name") or "Meal").strip()[:100] or "Meal"
        return ParsedMessage(
            intent=intent,
            meal_name=meal_name,
            macros=macros,
            is_estimation=bool(data.get("is_estimation", False)),
        )

    if intent == "UPDATE_GOALS":
        goals = {
            key: number
            for key in MACRO_KEYS
            if (number := _to_number(data.get(key), key, GOAL_LIMITS[key])) is not None
        }
        if not goals:
            raise ParseError("I couldn't find any goal values to update.")
        return ParsedMessage(intent=intent, macros=goals)

    if intent == "SET_TIMEZONE":
        timezone = str(data.get("timezone") or "").strip()
        if not is_valid_timezone(timezone):
            raise ParseError(
                "I couldn't recognize that timezone. Try a city-based name like "
                "America/New_York or Europe/London."
            )
        return ParsedMessage(intent=intent, timezone=timezone)

    if intent in SUMMARY_INTENTS:
        return ParsedMessage(intent=intent)

    return ParsedMessage(intent="OTHER")


def is_valid_timezone(name):
    if not name:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True
