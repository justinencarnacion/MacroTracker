import time
from collections import defaultdict, deque

import discord


class RateLimiter:
    """Allow at most `max_events` per user within a sliding `window_seconds`."""

    def __init__(self, max_events, window_seconds, clock=time.monotonic):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self.clock = clock
        self._events = defaultdict(deque)

    def allow(self, key):
        now = self.clock()
        events = self._events[key]
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True


class GuildMembershipChecker:
    """Only allow users who are members of one Discord server.

    Uses the REST member lookup, so the privileged "Server Members" intent is
    not required. Results are cached to avoid an API call per message.
    """

    def __init__(self, bot, guild_id, cache_seconds=600, clock=time.monotonic):
        self.bot = bot
        self.guild_id = guild_id
        self.cache_seconds = cache_seconds
        self.clock = clock
        self._cache = {}

    async def is_allowed(self, user_id):
        if self.guild_id is None:
            return True

        cached = self._cache.get(user_id)
        if cached and self.clock() < cached[1]:
            return cached[0]

        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            guild = await self.bot.fetch_guild(self.guild_id)
        try:
            await guild.fetch_member(user_id)
            allowed = True
        except discord.NotFound:
            allowed = False

        self._cache[user_id] = (allowed, self.clock() + self.cache_seconds)
        return allowed

    def forget(self, user_id):
        """Drop a cached answer, e.g. when the user has just joined the server."""
        self._cache.pop(user_id, None)
