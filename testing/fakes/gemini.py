"""A stand-in for the Gemini client: answers instantly and for free, and can be
told to be slow, overloaded, rate limited, or to return garbage.

It plugs in where the bot uses `client.aio.models.generate_content(...)`, and
raises the same google-genai errors the real service does, so the bot's model
fallback and error replies run exactly as in production.
"""

import asyncio
import json
import random
import re
from collections import Counter, defaultdict, deque
from types import SimpleNamespace

from google.genai import errors as genai_errors

# Rough per-item estimates (calories, protein, carbs, fat), enough to look real.
FOODS = {
    "egg": (78, 6, 1, 5),
    "toast": (80, 3, 14, 1),
    "chicken": (280, 50, 0, 8),
    "rice": (205, 4, 45, 0),
    "burrito": (650, 35, 70, 22),
    "bowl": (550, 30, 60, 18),
    "salad": (250, 8, 15, 18),
    "oatmeal": (300, 10, 54, 6),
    "banana": (105, 1, 27, 0),
    "protein shake": (160, 30, 5, 2),
    "pizza": (285, 12, 36, 10),
    "steak": (540, 46, 0, 38),
}
UNKNOWN_FOOD = (400, 20, 45, 15)

CITIES = {
    "new york": "America/New_York",
    "chicago": "America/Chicago",
    "denver": "America/Denver",
    "los angeles": "America/Los_Angeles",
    "london": "Europe/London",
    "tokyo": "Asia/Tokyo",
}

NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4}


def _macro(text, pattern):
    match = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{pattern})\b", text)
    return float(match.group(1)) if match else None


def _numbers(text):
    """Macros written out, e.g. '450 cals, 35p, 40c, 12f'."""
    return {
        "calories": _macro(text, r"k?cals?|kcal|calories"),
        "protein": _macro(text, r"p|g protein|protein"),
        "carbs": _macro(text, r"c|g carbs|carbs"),
        "fat": _macro(text, r"f|g fat|fat"),
    }


def _estimate(text):
    totals = [0, 0, 0, 0]
    found = False
    for food, macros in FOODS.items():
        match = re.search(rf"(?:\b(\d+|{'|'.join(NUMBER_WORDS)})\s+)?{food}", text)
        if match:
            found = True
            count = match.group(1)
            count = NUMBER_WORDS.get(count, int(count) if count else 1)
            totals = [total + value * count for total, value in zip(totals, macros)]
    return dict(zip(("calories", "protein", "carbs", "fat"), totals if found else UNKNOWN_FOOD))


def answer(text):
    """The JSON the real model is asked to return for this message."""
    lowered = text.lower().strip()
    nothing = {"calories": None, "protein": None, "carbs": None, "fat": None}

    if "goal" in lowered and re.search(r"\b(set|change|update)\b", lowered):
        return {"intent": "UPDATE_GOALS", **_numbers(lowered)}
    if "goal" in lowered:
        return {"intent": "SHOW_GOALS", **nothing}
    if "timezone" in lowered or lowered.startswith(("i'm in", "i am in")):
        city = next((zone for name, zone in CITIES.items() if name in lowered), "Mars/Olympus_Mons")
        return {"intent": "SET_TIMEZONE", "timezone": city, **nothing}
    if "today" in lowered or "left" in lowered:
        return {"intent": "SHOW_TODAY", **nothing}
    if "week" in lowered:
        return {"intent": "SHOW_WEEK", **nothing}

    numbers = _numbers(lowered)
    if any(value is not None for value in numbers.values()):
        return {"intent": "LOG_MEAL", "meal_name": "Manual entry", "is_estimation": False, **numbers}
    if re.match(r"(hi|hello|hey|thanks|help)\b", lowered):
        return {"intent": "OTHER", **nothing}
    return {"intent": "LOG_MEAL", "meal_name": text.strip()[:60].title(),
            "is_estimation": True, **_estimate(lowered)}


DAILY_QUOTA_DETAILS = [{
    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
}]


def api_error(code, daily_quota=False):
    """The error google-genai raises for an HTTP status code. A 429 is a
    per-minute limit unless `daily_quota`, which names the per-day quota in
    the error details the way Google does."""
    error_class = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    status = {429: "RESOURCE_EXHAUSTED", 503: "UNAVAILABLE"}.get(code, "ERROR")
    body = {"code": code, "message": "fake failure", "status": status}
    if daily_quota:
        body["details"] = DAILY_QUOTA_DETAILS
    return error_class(code, {"error": body})


class FakeGemini:
    """Pass as `ai_client` to MacroBot.

    latency, jitter: seconds each call takes (latency + up to jitter, random).
    daily_quota: calls per model before it answers 429, like the free tier.
    """

    def __init__(self, latency=0.0, jitter=0.0, daily_quota=None, seed=1):
        self.aio = SimpleNamespace(models=self)
        self.latency = latency
        self.jitter = jitter
        self.daily_quota = daily_quota
        self._random = random.Random(seed)
        self._down = {}  # model or "*" -> status code, until restore()
        self._scripted = defaultdict(deque)  # model or "*" -> upcoming failures
        self.calls = Counter()  # model -> calls received
        self.outcomes = Counter()  # (model, "ok" / status code / "garbage" / "daily_quota")
        self.in_flight = 0
        self.peak_in_flight = 0

    # --- controls ---------------------------------------------------------

    def outage(self, code=503, model="*"):
        """Every call to `model` ("*" = all models) fails until restore()."""
        self._down[model] = code

    def restore(self):
        self._down.clear()
        self._scripted.clear()

    def fail_next(self, times=1, code=503, model="*"):
        """The next `times` calls fail with `code`."""
        self._scripted[model].extend([code] * times)

    def garbage_next(self, times=1, model="*"):
        """The next `times` calls return text that isn't JSON."""
        self._scripted[model].extend(["garbage"] * times)

    # --- the API the bot calls ---------------------------------------------

    async def generate_content(self, model, contents, config=None):
        self.calls[model] += 1
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            delay = self.latency + self._random.uniform(0, self.jitter)
            if delay:
                await asyncio.sleep(delay)
            outcome = self._outcome(model)
            self.outcomes[(model, outcome)] += 1
            if outcome == "garbage":
                return SimpleNamespace(text="Sure! Here are your macros: lots of protein")
            if outcome == "daily_quota":
                raise api_error(429, daily_quota=True)
            if outcome != "ok":
                raise api_error(outcome)
            return SimpleNamespace(text=json.dumps(answer(contents)))
        finally:
            self.in_flight -= 1

    def _outcome(self, model):
        for key in (model, "*"):
            if self._scripted[key]:
                return self._scripted[key].popleft()
        for key in (model, "*"):
            if key in self._down:
                return self._down[key]
        if self.daily_quota is not None and self.calls[model] > self.daily_quota:
            return "daily_quota"
        return "ok"
