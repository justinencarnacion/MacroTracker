"""What the bot does when Gemini or Google Sheets fails, is slow, or runs out
of quota. Each scenario injects a fault into a fake, does something normal,
and checks the user is told the truth and no data is lost or corrupted."""

import asyncio

from testing.harness import MODELS
from testing.scenario import equal, expect, is_card, said, scenario

ALL_GOALS = {"calories": 2200, "protein": 180, "carbs": 220, "fat": 70}


def gemini_calls(harness):
    return sum(harness.gemini.calls.values())


def saved_meals(harness, user):
    return [row[1] for row in user.rows()] if harness.sheets.worksheets() else []


# --- Gemini ----------------------------------------------------------------

@scenario("First Gemini model down: falls back and logs the meal")
async def first_model_down(harness):
    alice = harness.user("Alice")
    harness.gemini.outage(503, model=MODELS[0])
    said(await alice.dm("banana"), "Logged!")
    equal(harness.gemini.outcomes[(MODELS[0], 503)], 1, "failed calls to the first model")
    equal(harness.gemini.outcomes[(MODELS[1], "ok")], 1, "answers from the second model")


@scenario("First Gemini model rate limited (429): falls back")
async def first_model_rate_limited(harness):
    alice = harness.user("Alice")
    harness.gemini.fail_next(code=429, model=MODELS[0])
    said(await alice.dm("banana"), "Logged!")
    equal(harness.counted("ai_call", f"{MODELS[0]}:rate_limited"), 1, "rate-limited metric")


@scenario("Every Gemini model down: 'busy' reply and nothing saved")
async def all_models_down(harness):
    alice = harness.user("Alice")
    harness.gemini.outage(503)
    said(await alice.dm("banana"), "AI service is busy")
    equal(gemini_calls(harness), len(MODELS), "Gemini calls (one per model)")
    equal(harness.sheets.worksheets(), [], "worksheet tabs")
    equal(harness.counted("request", "all_busy"), 1, "all_busy metric")


@scenario("Gemini comes back after an outage")
async def gemini_recovers(harness):
    alice = harness.user("Alice")
    harness.gemini.outage(503)
    said(await alice.dm("banana"), "AI service is busy")
    harness.gemini.restore()
    said(await alice.dm("banana"), "Logged!")


@scenario("A non-retryable Gemini error (400) doesn't waste calls on fallbacks")
async def bad_request_no_fallback(harness):
    alice = harness.user("Alice")
    harness.gemini.fail_next(code=400)
    said(await alice.dm("banana"), "could not process")
    equal(gemini_calls(harness), 1, "Gemini calls")


@scenario("Garbage from Gemini: nothing saved, user asked to rephrase")
async def garbage_answer(harness):
    alice = harness.user("Alice")
    harness.gemini.garbage_next()
    said(await alice.dm("banana"), "🤔", "2 eggs and toast")
    equal(harness.sheets.worksheets(), [], "worksheet tabs")
    equal(harness.counted("request", "unreadable"), 1, "unreadable metric")


@scenario("Per-minute limit on every model: 'try again in a minute'")
async def per_minute_limit(harness):
    alice = harness.user("Alice")
    harness.gemini.outage(429)
    said(await alice.dm("banana"), "try again in a minute")


@scenario("Daily quota used up: says when it resets, and summaries still work")
async def daily_quota_used_up(harness):
    harness.gemini.daily_quota = 1
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    for food in ("banana", "steak", "rice"):  # one answer per model, then all are out
        said(await alice.dm(food), "Logged!")
    reply = said(await alice.dm("pizza"), "resets at midnight Pacific", "/today")
    expect("try again in a minute" not in reply.text, "shouldn't suggest a minute's wait")
    is_card(await alice.slash("today"), "Banana", "Steak", "Rice")


# --- Google Sheets -----------------------------------------------------------

@scenario("Brief Sheets hiccup while logging: retried and saved, AI called once")
async def sheets_hiccup(harness):
    alice = harness.user("Alice")
    harness.sheets.fail_next(code=503)
    said(await alice.dm("banana"), "Logged!")
    equal(saved_meals(harness, alice), ["Banana"], "saved meals")
    equal(gemini_calls(harness), 1, "Gemini calls")


@scenario("Sheets down while logging: told plainly the meal wasn't saved")
async def sheets_down_logging(harness):
    alice = harness.user("Alice")
    harness.sheets.outage(503)
    reply = said(await alice.dm("2 eggs and toast"), "couldn't save", "2 Eggs And Toast",
                 "Google Sheets")
    expect("could not process" not in reply.text, "the meal was understood; don't say otherwise")
    equal(gemini_calls(harness), 1, "Gemini calls")
    harness.sheets.restore()
    equal(saved_meals(harness, alice), [], "saved meals")
    equal(harness.counted("request", "not_saved"), 1, "not_saved metric")


@scenario("Sheets comes back: logging works again")
async def sheets_recovers(harness):
    alice = harness.user("Alice")
    harness.sheets.outage(503)
    said(await alice.dm("banana"), "couldn't save")
    harness.sheets.restore()
    said(await alice.dm("banana"), "Logged!")
    equal(saved_meals(harness, alice), ["Banana"], "saved meals")


@scenario("Sheets down: /today, /week and buttons say Sheets is unavailable")
async def sheets_down_reading(harness):
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    alice.seed_meal("Oatmeal")
    card = await alice.slash("today")
    harness.sheets.outage(503)
    said(await alice.slash("today"), "Google Sheets isn't responding")
    said(await alice.slash("week"), "Google Sheets isn't responding")
    said(await alice.press(card, "Week"), "Google Sheets isn't responding")


@scenario("Sheets down when confirming a delete: meal kept, user told why")
async def sheets_down_deleting(harness):
    alice = harness.user("Alice")
    alice.seed_meal("Breakfast")
    confirm = await alice.choose(await alice.slash("delete"))
    harness.sheets.outage(503)
    said(await alice.press(confirm, "Delete"), "Google Sheets isn't responding")
    harness.sheets.restore()
    equal(saved_meals(harness, alice), ["Breakfast"], "meals")


@scenario("Goals and timezone still work while Sheets is down")
async def sheets_down_settings(harness):
    alice = harness.user("Alice")
    harness.sheets.outage(503)
    said(await alice.dm("set my goals to 2200 cals, 180p, 220c, 70f"), "Goals updated!")
    said(await alice.dm("set my timezone to London"), "Europe/London")
    said(await alice.slash("goals show"), "2,200 kcal")


# --- Slow services -----------------------------------------------------------

@scenario("Slow Sheets: slash commands and buttons still beat Discord's 3 seconds")
async def slow_sheets_deadline(harness):
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    alice.seed_meal("Oatmeal")
    harness.sheets.latency = 0.5
    card = is_card(await alice.slash("today"), "Oatmeal")  # the fake raises if it took > 3s to answer
    is_card(await alice.press(card, "Week"), "Daily average")


@scenario("Slow Sheets: quick messages from one person are saved to one tab")
async def slow_sheets_burst(harness):
    alice = harness.user("Alice")
    harness.sheets.latency = 0.02
    replies = await asyncio.gather(*(alice.dm(food) for food in ("banana", "steak", "rice")))
    for reply in replies:
        said(reply, "Logged!")
    equal(len(harness.sheets.worksheets()), 1, "worksheet tabs")
    equal(sorted(saved_meals(harness, alice)), ["Banana", "Rice", "Steak"], "saved meals")


@scenario("Slow Gemini: replies still arrive, one per message")
async def slow_gemini(harness):
    alice = harness.user("Alice")
    harness.gemini.latency = 0.3
    replies = await asyncio.gather(*(alice.dm(food) for food in ("banana", "steak")))
    for reply in replies:
        said(reply, "Logged!")
    equal(len(alice.inbox), 2, "replies")
