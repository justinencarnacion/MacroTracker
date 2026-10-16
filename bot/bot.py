import asyncio
from collections import defaultdict
from datetime import datetime
import logging
import os
from zoneinfo import ZoneInfo

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import discord
from discord.ext import commands
from google import genai

from bot.access import GuildMembershipChecker, RateLimiter
from bot.ai_parser import MACRO_KEYS, ParseError, is_overloaded, parse_input_with_ai
from bot.commands.summaries import SummaryCommands
from bot.replies import Replies, Reply
from bot.views.summary import SummaryView
from core.settings import Settings, SettingsError
from core.user_store import UserStore
from sheets.sheet_manager import connect_sheets, get_worksheet_for_user, worksheet_title
from tracking.service import TrackingService

logger = logging.getLogger("macrotracker")

HELP_TEXT = (
    "👋 I'm your macro tracker. DM me things like:\n"
    "• `2 eggs and toast` or `450 cals, 35p, 40c, 12f` — log a meal\n"
    "• `what did I eat today?` or `/today` — today's meals and what's left\n"
    "• `how's my week?` or `/week` — this week, Monday to Sunday\n"
    "• `set my goals to 2200 cals, 180p, 220c, 70f` or `/goals set` — daily goals\n"
    "• `what are my goals?` or `/goals show`\n"
    "• `set my timezone to America/New_York` — so meals land on the right day"
)


def format_macros(values):
    return (
        f"**Calories:** {values['calories']} kcal | **P:** {values['protein']}g | "
        f"**C:** {values['carbs']}g | **F:** {values['fat']}g"
    )


class MacroBot(commands.Bot):
    def __init__(self, settings):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.ai_client = genai.Client(api_key=settings.gemini_api_key)
        self.user_store = UserStore()
        self.spreadsheet = None
        self.rate_limiter = RateLimiter(
            settings.rate_limit_count, settings.rate_limit_seconds
        )
        self.membership = GuildMembershipChecker(self, settings.allowed_guild_id)
        self._user_locks = defaultdict(asyncio.Lock)
        self.tracking = None
        self.replies = None

    async def setup_hook(self):
        self.spreadsheet = await asyncio.to_thread(
            connect_sheets,
            self.settings.google_credentials,
            self.settings.sheet_name,
            self.settings.sheet_id,
        )
        logger.info("Connected to spreadsheet '%s'", self.spreadsheet.title)
        self.tracking = TrackingService(self.spreadsheet, self.settings.default_timezone)
        self.replies = Replies(self.tracking, self.user_store)

        await self.add_cog(SummaryCommands(self))
        self.add_view(SummaryView(self))  # keeps [Today] [Week] buttons working after restarts
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands: %s", len(synced),
                        ", ".join(f"/{command.name}" for command in synced))
        except discord.HTTPException:
            logger.exception("Could not sync slash commands; DMs still work")

    async def on_ready(self):
        logger.info("Logged in as %s; MacroTracker bot is online.", self.user)
        if self.settings.allowed_guild_id is None:
            logger.warning(
                "ALLOWED_GUILD_ID is not set; anyone who can DM the bot can use it."
            )

    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            return
        if not isinstance(message.channel, discord.DMChannel):
            return

        user_id = message.author.id
        try:
            refusal = await self.access_refusal(user_id)
            if refusal:
                await message.channel.send(refusal)
                return

            async with self.user_lock(user_id), message.channel.typing():
                reply = await self.handle_dm(message)
        except Exception as error:
            reply = self.error_reply(error, user_id)
        await message.channel.send(**Reply.of(reply).send_kwargs(self.summary_view))

    def summary_view(self, current):
        return SummaryView(self, current=current)

    async def switch_summary(self, interaction, kind):
        """[Today] / [Week] button: redraw the card in place with the presser's data."""
        await interaction.response.defer()
        user_id = interaction.user.id
        try:
            refusal = await self.access_refusal(user_id)
            if refusal:
                await interaction.followup.send(refusal, ephemeral=True)
                return
            user = await asyncio.to_thread(
                self.user_store.ensure_user, str(user_id),
                interaction.user.display_name.strip(),
            )
            build = self.replies.today if kind == "today" else self.replies.week
            async with self.user_lock(user_id):
                reply = Reply.of(await build(user))
            await interaction.edit_original_response(**reply.edit_kwargs(self.summary_view))
        except Exception as error:
            await interaction.followup.send(self.error_reply(error, user_id), ephemeral=True)

    async def access_refusal(self, user_id):
        """A refusal message if the user may not use the bot right now, else None."""
        if not await self.membership.is_allowed(user_id):
            return "🔒 This bot is only available to members of its Discord server."
        if not self.rate_limiter.allow(user_id):
            return "⏳ You're sending messages too quickly. Please wait a minute."
        return None

    def user_lock(self, user_id):
        """Serializes one user's requests so two quick messages can't race."""
        return self._user_locks[user_id]

    def error_reply(self, error, user_id):
        """The user-facing message for an error while handling a request."""
        if isinstance(error, ParseError):
            return f"🤔 {error}\n\n{HELP_TEXT}"
        if is_overloaded(error):
            logger.warning("All Gemini models unavailable for %s: %s", user_id, error)
            return "⏳ The AI service is busy right now. Please try again in a minute."
        logger.exception("Failed to process request for %s", user_id, exc_info=error)
        return "❌ I could not process that message. Please try again."

    async def handle_dm(self, message):
        discord_id = str(message.author.id)
        display_name = message.author.display_name.strip()
        user = await asyncio.to_thread(
            self.user_store.ensure_user, discord_id, display_name
        )
        parsed = await parse_input_with_ai(
            self.ai_client, self.settings.gemini_models, message.content
        )

        if parsed.intent == "UPDATE_GOALS":
            return await self.replies.set_goals(user, parsed.macros)

        if parsed.intent == "SHOW_TODAY":
            return await self.replies.today(user)

        if parsed.intent == "SHOW_WEEK":
            return await self.replies.week(user)

        if parsed.intent == "SHOW_GOALS":
            return await self.replies.goals(user)

        if parsed.intent == "SET_TIMEZONE":
            await asyncio.to_thread(
                self.user_store.set_timezone, discord_id, parsed.timezone
            )
            local_time = datetime.now(ZoneInfo(parsed.timezone)).strftime("%I:%M %p")
            return f"🕒 Timezone set to **{parsed.timezone}** (your time: {local_time})."

        if parsed.intent == "OTHER":
            return HELP_TEXT

        now = datetime.now(ZoneInfo(user["timezone"] or self.settings.default_timezone))
        values = [
            now.strftime("%Y-%m-%d %H:%M"),
            parsed.meal_name,
            *(parsed.macros[key] for key in MACRO_KEYS),
        ]
        await asyncio.to_thread(self._append_meal, user, values)

        source = "AI Estimated" if parsed.is_estimation else "Manual Input"
        logged = (
            f"✅ **Logged!** ({source})\n"
            f"**Meal:** {parsed.meal_name}\n{format_macros(parsed.macros)}"
        )
        user = await asyncio.to_thread(self.user_store.get, discord_id)
        left_today = await self.replies.left_today(user)
        return f"{logged}\n{left_today}" if left_today else logged

    def _append_meal(self, user, values):
        """Blocking Sheets work; always call through asyncio.to_thread."""
        sheet = get_worksheet_for_user(
            self.spreadsheet,
            user["worksheet_id"],
            worksheet_title(user["display_name"], user["discord_id"]),
        )
        if sheet.id != user["worksheet_id"]:
            self.user_store.set_worksheet_id(user["discord_id"], sheet.id)
        sheet.append_row(values)


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_env()
    except SettingsError as error:
        logger.error("Configuration error: %s", error)
        raise SystemExit(1)

    MacroBot(settings).run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
