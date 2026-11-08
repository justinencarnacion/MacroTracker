"""Everything a user can do by DMing the bot in plain English."""

from datetime import datetime
from zoneinfo import ZoneInfo

from testing.scenario import equal, expect, is_card, not_said, said, scenario

GOALS = "set my goals to 2200 cals, 180p, 220c, 70f"


@scenario("Describing food logs an AI estimate to the sheet")
async def log_estimate(harness):
    alice = harness.user("Alice")
    said(await alice.dm("2 eggs and toast"), "Logged!", "AI Estimated", "2 Eggs And Toast", "236 kcal")
    equal(alice.rows()[0][1:], ["2 Eggs And Toast", 236, 15, 16, 11], "saved row")
    equal(harness.counted("meal", "logged"), 1, "meal:logged metric")


@scenario("Exact numbers are logged as typed")
async def log_manual(harness):
    alice = harness.user("Alice")
    said(await alice.dm("450 cals, 35p, 40c, 12f"), "Logged!", "Manual Input", "450 kcal")
    equal(alice.rows()[0][2:], [450, 35, 40, 12], "saved macros")


@scenario("Impossible numbers are rejected and nothing is saved")
async def log_impossible(harness):
    alice = harness.user("Alice")
    said(await alice.dm("99999 cals"), "looks wrong")
    equal(harness.sheets.worksheets(), [], "worksheet tabs")


@scenario("Logging shows what's left once goals are set")
async def left_after_logging(harness):
    alice = harness.user("Alice")
    said(await alice.dm("banana"), "Set your goals")
    await alice.dm(GOALS)
    reply = said(await alice.dm("banana"), "Left today", "1,990 kcal")
    not_said(reply, "Set your goals")


@scenario("First-time goals need all four macros")
async def first_goals_need_all(harness):
    alice = harness.user("Alice")
    said(await alice.dm("set my goals to 2200 cals"), "all four", "protein, carbs, fat")
    said(await alice.dm("what are my goals?"), "Set your daily goals first")


@scenario("Goals can be set, shown, and partly changed by DM")
async def goals_by_dm(harness):
    alice = harness.user("Alice")
    said(await alice.dm(GOALS), "Goals updated!", "2,200 kcal", "180g")
    said(await alice.dm("set my goals to 2000 cals"), "Goals updated!", "2,000 kcal", "180g")
    said(await alice.dm("what are my goals?"), "Your daily goals", "2,000 kcal", "70g")


@scenario("A timezone can be set, and meals use that local time")
async def timezone_applies(harness):
    alice = harness.user("Alice")
    said(await alice.dm("set my timezone to Tokyo"), "Asia/Tokyo")
    before = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H")
    await alice.dm("banana")
    after = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H")
    expect(alice.rows()[0][0][:13] in (before, after),
           f"meal time {alice.rows()[0][0]!r} isn't Tokyo time ({before})")


@scenario("An unrecognized timezone is refused and not saved")
async def timezone_invalid(harness):
    alice = harness.user("Alice")
    said(await alice.dm("set my timezone to Narnia"), "couldn't recognize that timezone")
    expect(harness.bot.user_store.get(alice.id)["timezone"] is None, "no timezone should be saved")


@scenario("Asking about today or the week returns the chart cards")
async def summaries_by_dm(harness):
    alice = harness.user("Alice")
    await alice.dm(GOALS)
    await alice.dm("banana")
    is_card(await alice.dm("what did I eat today?"), "Banana")
    is_card(await alice.dm("how's my week going?"), "Daily average")


@scenario("Summaries before goals ask the user to set them")
async def summaries_need_goals(harness):
    alice = harness.user("Alice")
    said(await alice.dm("what did I eat today?"), "Set your daily goals first")
    said(await alice.dm("how's my week?"), "Set your daily goals first")


@scenario("Greetings get the help text and log nothing")
async def greeting(harness):
    alice = harness.user("Alice")
    said(await alice.dm("hello"), "I'm your macro tracker", "/help")
    equal(harness.sheets.worksheets(), [], "worksheet tabs")


@scenario("Changing Discord name keeps the same meal tab")
async def rename_keeps_tab(harness):
    alice = harness.user("Alice")
    await alice.dm("banana")
    original_tab = alice.tab
    alice.user.display_name = "Alicia"
    await alice.dm("steak")
    equal(len(harness.sheets.worksheets()), 1, "worksheet tabs")
    equal([row[1] for row in alice.rows(original_tab)], ["Banana", "Steak"], "meals")
