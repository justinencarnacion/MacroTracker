import asyncio
import unittest
from types import SimpleNamespace

import discord

from bot.access import GuildMembershipChecker, RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class RateLimiterTests(unittest.TestCase):
    def test_blocks_after_limit_and_recovers_after_window(self):
        clock = FakeClock()
        limiter = RateLimiter(2, 60, clock=clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))
        clock.now = 60
        self.assertTrue(limiter.allow("a"))


class FakeGuild:
    def __init__(self, member_ids):
        self.member_ids = member_ids
        self.lookups = 0

    async def fetch_member(self, user_id):
        self.lookups += 1
        if user_id not in self.member_ids:
            raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "Unknown Member")
        return object()


class GuildMembershipCheckerTests(unittest.TestCase):
    def test_allows_members_and_caches_results(self):
        guild = FakeGuild({1})
        bot = SimpleNamespace(get_guild=lambda guild_id: guild)
        checker = GuildMembershipChecker(bot, 99)

        self.assertTrue(asyncio.run(checker.is_allowed(1)))
        self.assertFalse(asyncio.run(checker.is_allowed(2)))
        asyncio.run(checker.is_allowed(1))
        self.assertEqual(guild.lookups, 2)

    def test_forget_clears_a_cached_refusal(self):
        guild = FakeGuild(set())
        checker = GuildMembershipChecker(SimpleNamespace(get_guild=lambda guild_id: guild), 99)
        self.assertFalse(asyncio.run(checker.is_allowed(5)))
        guild.member_ids.add(5)  # they joined
        self.assertFalse(asyncio.run(checker.is_allowed(5)))  # still cached
        checker.forget(5)
        self.assertTrue(asyncio.run(checker.is_allowed(5)))

    def test_no_guild_configured_allows_everyone(self):
        checker = GuildMembershipChecker(SimpleNamespace(), None)
        self.assertTrue(asyncio.run(checker.is_allowed(123)))


if __name__ == "__main__":
    unittest.main()
