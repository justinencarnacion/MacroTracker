"""Reply text for summary and goal requests, shared by DMs and slash commands."""

import asyncio
import logging

from bot import formatting
from tracking.goals import GoalsIncomplete, has_goals, merge_goals

logger = logging.getLogger(__name__)


class Replies:
    def __init__(self, tracking, user_store):
        self.tracking = tracking
        self.user_store = user_store

    async def today(self, user):
        if not has_goals(user["goals"]):
            return formatting.NEEDS_GOALS_TEXT
        summary = await asyncio.to_thread(self.tracking.day_summary, user, user["goals"])
        return formatting.format_day(summary)

    async def week(self, user):
        if not has_goals(user["goals"]):
            return formatting.NEEDS_GOALS_TEXT
        summary = await asyncio.to_thread(self.tracking.week_summary, user, user["goals"])
        return formatting.format_week(summary)

    async def goals(self, user):
        if not has_goals(user["goals"]):
            return formatting.NEEDS_GOALS_TEXT
        return formatting.format_goals(user["goals"])

    async def set_goals(self, user, updates):
        try:
            goals = merge_goals(user["goals"], updates)
        except GoalsIncomplete as error:
            return f"🤔 {error}"
        await asyncio.to_thread(self.user_store.set_goals, user["discord_id"], goals)
        return formatting.format_goals_updated(goals)

    async def left_today(self, user):
        """One line for after a meal is logged. Never raises: logging already succeeded."""
        if not has_goals(user["goals"]):
            return formatting.SET_GOALS_HINT
        try:
            summary = await asyncio.to_thread(
                self.tracking.day_summary, user, user["goals"]
            )
        except Exception:
            logger.exception("Could not compute today's remaining macros for %s",
                             user["discord_id"])
            return ""
        return formatting.format_left_today(summary.remaining)
