"""Reply content for summary and goal requests, shared by DMs, slash commands, and buttons."""

import asyncio
import io
import logging
from dataclasses import dataclass

import discord

from bot import embeds, formatting
from charts.today import render_today
from charts.week import render_week
from tracking.goals import GoalsIncomplete, has_goals, merge_goals

logger = logging.getLogger(__name__)


@dataclass
class Reply:
    """What to send: text, an embed card, an attached chart image, and which
    summary buttons to show ("today" / "week", or None for no buttons)."""

    content: str | None = None
    embed: discord.Embed | None = None
    image: bytes | None = None
    image_name: str | None = None
    buttons: str | None = None
    view: discord.ui.View | None = None  # a one-off view (e.g. a meal picker); overrides `buttons`

    @classmethod
    def of(cls, value):
        return value if isinstance(value, cls) else cls(content=value)

    def file(self):
        if self.image is None:
            return None
        return discord.File(io.BytesIO(self.image), filename=self.image_name)

    def _view(self, make_view):
        if self.view is not None:
            return self.view
        return make_view(self.buttons) if self.buttons else None

    def send_kwargs(self, make_view):
        """Keyword arguments for channel.send / followup.send. Discord files are
        single-use, so a fresh File is created on every call."""
        kwargs = {
            "content": self.content,
            "embed": self.embed,
            "file": self.file(),
            "view": self._view(make_view),
        }
        return {key: value for key, value in kwargs.items() if value is not None}

    def edit_kwargs(self, make_view):
        """Keyword arguments for editing an existing message in place."""
        file = self.file()
        return {
            "content": self.content,
            "embed": self.embed,
            "attachments": [file] if file else [],
            "view": self._view(make_view),
        }


class Replies:
    def __init__(self, tracking, user_store):
        self.tracking = tracking
        self.user_store = user_store

    async def today(self, user):
        if not has_goals(user["goals"]):
            return Reply(content=formatting.NEEDS_GOALS_TEXT)
        summary = await asyncio.to_thread(self.tracking.day_summary, user, user["goals"])
        try:
            image = await asyncio.to_thread(render_today, summary)
        except Exception:
            logger.exception("Could not draw today's chart; sending text instead")
            return Reply(content=formatting.format_day(summary), buttons="today")
        return Reply(embed=embeds.today_embed(summary), image=image,
                     image_name=embeds.TODAY_IMAGE, buttons="today")

    async def week(self, user):
        if not has_goals(user["goals"]):
            return Reply(content=formatting.NEEDS_GOALS_TEXT)
        summary = await asyncio.to_thread(self.tracking.week_summary, user, user["goals"])
        try:
            image = await asyncio.to_thread(render_week, summary)
        except Exception:
            logger.exception("Could not draw this week's chart; sending text instead")
            return Reply(content=formatting.format_week(summary), buttons="week")
        return Reply(embed=embeds.week_embed(summary), image=image,
                     image_name=embeds.WEEK_IMAGE, buttons="week")

    async def after_change(self, user, message):
        """A confirmation line followed by the refreshed /today card."""
        reply = Reply.of(await self.today(user))
        reply.content = f"{message}\n\n{reply.content}" if reply.content else message
        return reply

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
