"""/edit and /delete: dropdown, form, confirmation, and sheet safety."""

from sheets.sheet_manager import update_meal
from testing.scenario import equal, expect, is_card, said, scenario

ALL_GOALS = {"calories": 2200, "protein": 180, "carbs": 220, "fat": 70}


def names(user):
    return [row[1] for row in user.rows()]


@scenario("/edit and /delete say so when there's nothing to change")
async def nothing_to_change(harness):
    alice = harness.user("Alice")
    for command in ("edit", "delete"):
        said(await alice.slash(command), "No meals logged in the last 7 days")


@scenario("/edit changes the meal and keeps its original time")
async def edit_saves(harness):
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    alice.seed_meal("Burger", calories=800, time="09:15")
    original_time = alice.rows()[0][0]

    picker = said(await alice.slash("edit"), "Which meal do you want to edit?")
    form = await alice.choose(picker)
    equal(form.via, "modal", "choosing a meal")
    confirm = said(await alice.submit(form, meal_name="Small burger", calories="600"),
                   "Save these changes", "Calories: 800 kcal → 600 kcal", "Name: Burger → Small burger")
    equal(alice.rows()[0][1:3], ["Burger", 800], "sheet before confirming")

    is_card(await alice.press(confirm, "Save"), "Updated", "Small burger", "600 / 2,200")
    equal(alice.rows()[0][:3], [original_time, "Small burger", 600], "saved row")
    equal(harness.counted("meal", "edited"), 1, "meal:edited metric")


@scenario("Edit form rejects bad numbers and saves nothing")
async def edit_invalid(harness):
    alice = harness.user("Alice")
    alice.seed_meal("Burger", calories=800)
    form = await alice.choose(await alice.slash("edit"))
    reply = said(await alice.submit(form, calories="lots"), "must be a number", "Nothing was changed")
    expect(reply.ephemeral, "the error should be private")
    equal(alice.rows()[0][2], 800, "calories")


@scenario("Submitting the form unchanged saves nothing")
async def edit_no_changes(harness):
    alice = harness.user("Alice")
    alice.seed_meal("Burger", calories=800)
    form = await alice.choose(await alice.slash("edit"))
    said(await alice.submit(form), "No changes")
    equal(alice.rows()[0][2], 800, "calories")


@scenario("/delete removes only the chosen meal, after confirming")
async def delete_saves(harness):
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    alice.seed_meal("Breakfast", time="08:00")
    alice.seed_meal("Lunch", time="12:00")

    picker = said(await alice.slash("delete"), "Which meal do you want to delete?")
    confirm = said(await alice.choose(picker), "Delete **Lunch**")  # newest is listed first
    equal(names(alice), ["Breakfast", "Lunch"], "sheet before confirming")

    is_card(await alice.press(confirm, "Delete"), "Deleted", "Breakfast")
    equal(names(alice), ["Breakfast"], "meals")
    equal(harness.counted("meal", "deleted"), 1, "meal:deleted metric")


@scenario("Cancel leaves the meal alone")
async def delete_cancel(harness):
    alice = harness.user("Alice")
    alice.seed_meal("Breakfast")
    confirm = await alice.choose(await alice.slash("delete"))
    said(await alice.press(confirm, "Cancel"), "Cancelled")
    equal(names(alice), ["Breakfast"], "meals")


@scenario("Only the person who opened a menu can use it")
async def owner_only(harness):
    alice, bob = harness.user("Alice"), harness.user("Bob")
    alice.seed_meal("Breakfast")
    picker = await alice.slash("delete")
    confirm = await alice.choose(picker)
    said(await bob.press(confirm, "Delete"), "belongs to someone else")
    equal(names(alice), ["Breakfast"], "meals")


@scenario("A meal that moved in the sheet is still found")
async def moved_meal(harness):
    alice = harness.user("Alice")
    await alice.slash("goals set", **ALL_GOALS)
    sheet = alice.seed_meal("Breakfast", time="08:00")
    alice.seed_meal("Lunch", time="12:00")
    alice.seed_meal("Dinner", time="18:00")
    confirm = said(await alice.choose(await alice.slash("delete")), "Delete **Dinner**")

    sheet.delete_rows(2)  # someone removes Breakfast by hand, shifting every row up
    await alice.press(confirm, "Delete")
    equal(names(alice), ["Lunch"], "meals")


@scenario("A meal changed since it was picked is left untouched")
async def changed_meal(harness):
    alice = harness.user("Alice")
    sheet = alice.seed_meal("Breakfast")
    confirm = await alice.choose(await alice.slash("delete"))

    update_meal(sheet, 2, "Hand edited", 111, 1, 1, 1)
    said(await alice.press(confirm, "Delete"), "changed or moved", "nothing was changed")
    equal(names(alice), ["Hand edited"], "meals")


@scenario("The picker covers the last 7 days only")
async def seven_day_window(harness):
    alice = harness.user("Alice")
    alice.seed_meal("Too old", days_ago=7)
    alice.seed_meal("Just in time", days_ago=6)
    picker = await alice.slash("edit")
    equal(len(picker.view.select.options), 1, "options")
    expect("Just in time" in picker.view.select.options[0].label, "the 6-day-old meal should be listed")


@scenario("Over 25 meals are capped to Discord's dropdown limit")
async def picker_limit(harness):
    alice = harness.user("Alice")
    for minute in range(30):
        alice.seed_meal(f"Snack {minute}", time=f"08:{minute:02d}")
    picker = said(await alice.slash("delete"), "Showing the 25 most recent")
    equal(len(picker.view.select.options), 25, "options")
