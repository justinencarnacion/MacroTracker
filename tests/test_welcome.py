import asyncio
import unittest
from collections import Counter
from types import SimpleNamespace

import discord

from bot.bot import MacroBot
from bot.commands.help import HelpCommands
from bot.welcome import GUIDE

GUILD_ID = 42


class FakeMetrics:
    def __init__(self):
        self.counts = Counter()

    def incr(self, name, label):
        self.counts[(name, label)] += 1


class FakeMembership:
    def __init__(self):
        self.forgotten = []

    def forget(self, user_id):
        self.forgotten.append(user_id)


class FakeMember:
    def __init__(self, member_id=7, guild_id=GUILD_ID, is_bot=False, dms_closed=False):
        self.id = member_id
        self.bot = is_bot
        self.guild = SimpleNamespace(id=guild_id)
        self.dms_closed = dms_closed
        self.sent = []

    async def send(self, text):
        if self.dms_closed:
            raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Cannot send messages to this user")
        self.sent.append(text)


def fake_bot(allowed_guild_id=GUILD_ID):
    return SimpleNamespace(settings=SimpleNamespace(allowed_guild_id=allowed_guild_id),
                           metrics=FakeMetrics(), membership=FakeMembership())


def join(bot, member):
    asyncio.run(MacroBot.on_member_join(bot, member))


class GuideTests(unittest.TestCase):
    def test_fits_in_one_discord_message(self):
        self.assertLess(len(GUIDE), 2000)

    def test_covers_setup_logging_and_progress(self):
        for text in ("/goals set", "set my timezone", "2 eggs and toast",
                     "/today", "/week", "/edit", "/delete", "/help"):
            self.assertIn(text, GUIDE)


class WelcomeOnJoinTests(unittest.TestCase):
    def test_new_member_gets_the_guide(self):
        bot, member = fake_bot(), FakeMember()
        join(bot, member)
        self.assertEqual(member.sent, [GUIDE])
        self.assertEqual(bot.metrics.counts[("welcome", "sent")], 1)
        self.assertEqual(bot.membership.forgotten, [member.id])

    def test_closed_dms_are_counted_not_raised(self):
        bot, member = fake_bot(), FakeMember(dms_closed=True)
        join(bot, member)
        self.assertEqual(bot.metrics.counts[("welcome", "dms_closed")], 1)

    def test_ignores_other_servers_and_bots(self):
        bot = fake_bot()
        for member in (FakeMember(guild_id=999), FakeMember(is_bot=True)):
            join(bot, member)
            self.assertEqual(member.sent, [])
        self.assertEqual(sum(bot.metrics.counts.values()), 0)

    def test_any_server_when_no_server_is_configured(self):
        bot, member = fake_bot(allowed_guild_id=None), FakeMember(guild_id=999)
        join(bot, member)
        self.assertEqual(member.sent, [GUIDE])


class HelpCommandTests(unittest.TestCase):
    def test_help_command_is_registered_for_dms_and_servers(self):
        command = HelpCommands(SimpleNamespace()).get_app_commands()[0]
        self.assertEqual(command.name, "help")
        self.assertTrue(command.allowed_contexts.guild and command.allowed_contexts.dm_channel)


if __name__ == "__main__":
    unittest.main()
