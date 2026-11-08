"""/today, /week, /goals, and the [Today] [Week] buttons."""

from testing.scenario import equal, expect, is_card, not_said, said, scenario

ALL_GOALS = {"calories": 2200, "protein": 180, "carbs": 220, "fat": 70}


async def member_with_goals(harness, name="Alice"):
    user = harness.user(name)
    await user.slash("goals set", **ALL_GOALS)
    return user


@scenario("/goals set needs all four the first time, then any")
async def goals_set(harness):
    alice = harness.user("Alice")
    said(await alice.slash("goals set", calories=2000), "all four")
    said(await alice.slash("goals set", **ALL_GOALS), "Goals updated!", "2,200 kcal")
    said(await alice.slash("goals set", fat=60), "Goals updated!", "2,200 kcal", "60g")
    said(await alice.slash("goals show"), "Your daily goals", "60g")


@scenario("/goals set with no values explains what to do")
async def goals_set_empty(harness):
    alice = harness.user("Alice")
    reply = said(await alice.slash("goals set"), "Include at least one value")
    expect(reply.ephemeral, "the hint should be private")


@scenario("/goals show, /today and /week ask for goals first")
async def need_goals(harness):
    alice = harness.user("Alice")
    for command in ("goals show", "today", "week"):
        said(await alice.slash(command), "Set your daily goals first")


@scenario("/today shows meals, progress, a chart and buttons")
async def today_card(harness):
    alice = await member_with_goals(harness)
    alice.seed_meal("Oatmeal", calories=300)
    alice.seed_meal("Chicken", calories=400, time="12:00")
    card = is_card(await alice.slash("today"), "Oatmeal", "Chicken", "700 / 2,200")
    expect(card.view.today_button.disabled, "Today should be disabled on the Today card")
    expect(not card.view.week_button.disabled, "Week should be pressable on the Today card")


@scenario("/today leaves out yesterday's meals")
async def today_only_today(harness):
    alice = await member_with_goals(harness)
    alice.seed_meal("Old dinner", calories=900, days_ago=1)
    alice.seed_meal("Breakfast", calories=300)
    not_said(is_card(await alice.slash("today"), "Breakfast", "300 / 2,200"), "Old dinner")


@scenario("/week totals this week only")
async def week_card(harness):
    alice = await member_with_goals(harness)
    alice.seed_meal("Two weeks ago", calories=900, days_ago=14)
    alice.seed_meal("Today", calories=500)
    card = is_card(await alice.slash("week"), "Daily average")
    calories = next(item.value for item in card.embed.fields if item.name == "Calories")
    expect(calories.startswith("500 /"), f"week calories should start at 500: {calories!r}")


@scenario("Slash replies are private in servers and normal in DMs")
async def privacy(harness):
    alice = await member_with_goals(harness)
    for command in ("today", "week", "goals show"):
        expect(not (await alice.slash(command)).ephemeral, f"/{command} in DMs")
        expect((await alice.slash(command, in_server=True)).ephemeral, f"/{command} in a server")


@scenario("The buttons switch one card between Today and Week")
async def buttons_switch(harness):
    alice = await member_with_goals(harness)
    alice.seed_meal("Oatmeal")
    today = await alice.slash("today")
    week = is_card(await alice.press(today, "Week"), "Daily average")
    equal(week.via, "edit", "Week button")
    expect(week.view.week_button.disabled, "Week should be disabled on the Week card")
    back = is_card(await alice.press(week, "Today"), "Oatmeal")
    equal(back.via, "edit", "Today button")


@scenario("Pressing someone else's button shows your own data")
async def buttons_show_presser(harness):
    alice = await member_with_goals(harness, "Alice")
    bob = await member_with_goals(harness, "Bob")
    alice.seed_meal("Alices lunch")
    bob.seed_meal("Bobs lunch")
    alices_week = await alice.slash("week")
    not_said(is_card(await bob.press(alices_week, "Today"), "Bobs lunch"), "Alices lunch")
