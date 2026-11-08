"""Joining the server, the welcome guide, /help, and who may use the bot."""

import asyncio

from bot.welcome import GUIDE
from testing.scenario import equal, expect, said, scenario


@scenario("A new member is DMed the guide when they join")
async def welcome_on_join(harness):
    newcomer = harness.user("Newcomer", member=False)
    welcome = await newcomer.join()
    equal(welcome.content, GUIDE, "welcome DM")
    equal(harness.counted("welcome", "sent"), 1, "welcome:sent metric")


@scenario("A member with closed DMs joins without causing an error")
async def closed_dms(harness):
    newcomer = harness.user("Private", member=False, accepts_dms=False)
    equal(await newcomer.join(), None, "reply")
    equal(harness.counted("welcome", "dms_closed"), 1, "welcome:dms_closed metric")


@scenario("Other bots joining aren't welcomed")
async def bots_not_welcomed(harness):
    other_bot = harness.user("SomeBot", member=False, is_bot=True)
    equal(await other_bot.join(), None, "reply")


@scenario("Someone refused earlier can use the bot right after joining")
async def refused_then_joins(harness):
    person = harness.user("Late", member=False)
    said(await person.dm("hello"), "only available to members")
    await person.join()
    said(await person.dm("hello"), "macro tracker")


@scenario("/help shows the guide in DMs, and privately in the server")
async def help_command(harness):
    alice = harness.user("Alice")
    dm = await alice.slash("help")
    equal(dm.content, GUIDE, "/help")
    expect(not dm.ephemeral, "/help in DMs should be a normal message")
    expect((await alice.slash("help", in_server=True)).ephemeral, "/help in a server should be private")


@scenario("Non-members are refused everywhere and spend no AI quota")
async def non_member_refused(harness):
    outsider = harness.user("Eve", member=False)
    member = harness.user("Alice")
    await member.dm("set my goals to 2200 cals, 180p, 220c, 70f")
    card = await member.slash("week")
    calls = sum(harness.gemini.calls.values())

    said(await outsider.dm("2 eggs"), "only available to members")
    said(await outsider.slash("today"), "only available to members")
    said(await outsider.press(card, "Today"), "only available to members")
    equal(sum(harness.gemini.calls.values()), calls, "Gemini calls")
    expect(harness.counted("refused", "not_member") >= 1, "refusals should be counted")


@scenario("Messages from bots and in server channels are ignored")
async def ignored_messages(harness):
    other_bot = harness.user("SomeBot", is_bot=True)
    alice = harness.user("Alice")
    equal(await other_bot.dm("2 eggs"), None, "reply to a bot")
    equal(await alice.say_in_server("2 eggs"), None, "reply in a server channel")
    equal(sum(harness.gemini.calls.values()), 0, "Gemini calls")


@scenario("The 11th message in a minute is refused, for that user only", rate_limit=(10, 60))
async def rate_limit(harness):
    alice, bob = harness.user("Alice"), harness.user("Bob")
    for _ in range(10):
        said(await alice.dm("hello"), "macro tracker")
    said(await alice.dm("hello"), "too quickly")
    equal(sum(harness.gemini.calls.values()), 10, "Gemini calls")
    said(await bob.dm("hello"), "macro tracker")


@scenario("Two members at once keep their meals separate")
async def separate_users(harness):
    alice, bob = harness.user("Alice"), harness.user("Bob")
    await asyncio.gather(alice.dm("2 eggs and toast"), bob.dm("steak"))
    equal([row[1] for row in alice.rows()], ["2 Eggs And Toast"], "Alice's meals")
    equal([row[1] for row in bob.rows()], ["Steak"], "Bob's meals")


@scenario("Five quick messages from one person are all saved to one tab")
async def same_user_burst(harness):
    alice = harness.user("Alice")
    await asyncio.gather(*(alice.dm(f"{count} eggs") for count in range(1, 6)))
    equal(len(alice.rows()), 5, "saved meals")
    equal(len(harness.sheets.worksheets()), 1, "worksheet tabs")
