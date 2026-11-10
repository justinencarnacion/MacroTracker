import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import logging
import os
from zoneinfo import ZoneInfo

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import discord
from discord.ext import commands
from google import genai

from bot.access import GuildMembershipChecker, RateLimiter
from bot.ai_parser import (MACRO_KEYS, ParseError, is_daily_quota, is_overloaded,
                           parse_input_with_ai)
from bot.commands.help import HelpCommands
from bot.commands.meals import MealCommands
from bot.commands.summaries import SummaryCommands
from bot.replies import Replies, Reply
from bot.views.meals import changes, describe_ref
from bot.views.summary import SummaryView
from bot.welcome import GUIDE
from core.metrics import Metrics
from core.settings import Settings, SettingsError
from core.user_store import UserStore
from sheets.sheet_manager import (connect_sheets, get_worksheet_for_user, is_temporary_error,
                                  worksheet_title)
from tracking.meal_service import MealChanged, MealService
from tracking.service import TrackingService

logger = logging.getLogger("macrotracker")

QUOTA_TIMEZONE = ZoneInfo("America/Los_Angeles")  # Gemini's daily quota resets at midnight here

HELP_TEXT = (
    "👋 I'm your macro tracker. DM me things like:\n"
    "• `2 eggs and toast` or `450 cals, 35p, 40c, 12f` — log a meal\n"
    "• `what did I eat today?` or `/today` — today's meals and what's left\n"
    "• `how's my week?` or `/week` — this week, Monday to Sunday\n"
    "• `set my goals to 2200 cals, 180p, 220c, 70f` or `/goals set` — daily goals\n"
    "• `what are my goals?` or `/goals show`\n"
    "• `/edit` or `/delete` — fix a meal from the last 7 days\n"
    "• `/help` — the full getting-started guide\n"
    "• `set my timezone to America/New_York` — so meals land on the right day"
)


class MealNotSaved(Exception):
    """Gemini understood the meal, but writing it to Sheets failed."""

    def __init__(self, parsed):
        super().__init__(f"Could not save {parsed.meal_name!r}")
        self.parsed = parsed


def until_quota_reset(now=None):
    """'about 5 hours' / 'under an hour': time until midnight Pacific."""
    now = now or datetime.now(QUOTA_TIMEZONE)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    hours = round((midnight - now).total_seconds() / 3600)
    if hours < 1:
        return "under an hour"
    return "about 1 hour" if hours == 1 else f"about {hours} hours"


def format_macros(values):
    return (
        f"**Calories:** {values['calories']} kcal | **P:** {values['protein']}g | "
        f"**C:** {values['carbs']}g | **F:** {values['fat']}g"
    )


class MacroBot(commands.Bot):
    def __init__(self, settings, welcome_new_members=True, *, ai_client=None,
                 user_store=None, spreadsheet=None):
        intents = discord.Intents.default()
        intents.message_content = True
        # Seeing members join needs the privileged "Server Members Intent"
        # (Developer Portal -> Bot). main() falls back without it if it's off.
        intents.members = welcome_new_members
        super().__init__(command_prefix="!", intents=intents)
        self.welcome_new_members = welcome_new_members

        self.settings = settings
        # The simulated test runs (testing/) pass fakes for these three;
        # normally the real Gemini client, database, and spreadsheet are used.
        self.ai_client = ai_client or genai.Client(api_key=settings.gemini_api_key)
        self.user_store = user_store or UserStore()
        self.spreadsheet = spreadsheet
        self.rate_limiter = RateLimiter(
            settings.rate_limit_count, settings.rate_limit_seconds
        )
        self.membership = GuildMembershipChecker(self, settings.allowed_guild_id)
        self._user_locks = defaultdict(asyncio.Lock)
        self.metrics = Metrics(self.user_store.database_path)
        # Seconds to wait before each retry of a meal save that hit a brief Sheets error.
        self.save_retry_delays = (1, 3)
        self._metrics_task = None
        self.tracking = None
        self.replies = None
        self.meals = None

    async def setup_hook(self):
        self._metrics_task = asyncio.create_task(self._save_metrics_every_minute())
        await self.connect_services()

        await self.add_cog(SummaryCommands(self))
        await self.add_cog(MealCommands(self))
        await self.add_cog(HelpCommands(self))
        self.add_view(SummaryView(self))  # keeps [Today] [Week] buttons working after restarts
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d slash commands: %s", len(synced),
                        ", ".join(f"/{command.name}" for command in synced))
        except discord.HTTPException:
            logger.exception("Could not sync slash commands; DMs still work")

    async def connect_services(self):
        """Open the spreadsheet (unless one was passed in) and build the services
        that read and write it. Needs no Discord connection."""
        if self.spreadsheet is None:
            self.spreadsheet = await asyncio.to_thread(
                connect_sheets,
                self.settings.google_credentials,
                self.settings.sheet_name,
                self.settings.sheet_id,
            )
        logger.info("Connected to spreadsheet '%s'", self.spreadsheet.title)
        self.tracking = TrackingService(self.spreadsheet, self.settings.default_timezone)
        self.replies = Replies(self.tracking, self.user_store)
        self.meals = MealService(self.spreadsheet, self.tracking)

    async def on_ready(self):
        logger.info("Logged in as %s; MacroTracker bot is online.", self.user)
        if not self.welcome_new_members:
            logger.warning("Welcome DMs for new members are off (Server Members Intent not enabled)")
        if self.settings.allowed_guild_id is None:
            logger.warning(
                "ALLOWED_GUILD_ID is not set; anyone who can DM the bot can use it."
            )

    async def on_member_join(self, member):
        """DM the getting-started guide to people who join the bot's server."""
        allowed = self.settings.allowed_guild_id
        if member.bot or (allowed is not None and member.guild.id != allowed):
            return
        self.membership.forget(member.id)  # they're a member now, even if refused earlier
        try:
            await member.send(GUIDE)
            self.metrics.incr("welcome", "sent")
            logger.info("Sent welcome guide to new member %s", member.id)
        except discord.Forbidden:
            self.metrics.incr("welcome", "dms_closed")
            logger.info("New member %s doesn't accept DMs; no welcome sent", member.id)
        except discord.HTTPException:
            self.metrics.incr("welcome", "failed")
            logger.exception("Could not send welcome guide to %s", member.id)

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
            self.metrics.incr("button", kind)
            build = self.replies.today if kind == "today" else self.replies.week
            async with self.user_lock(user_id):
                reply = Reply.of(await build(user))
            await interaction.edit_original_response(**reply.edit_kwargs(self.summary_view))
        except Exception as error:
            await interaction.followup.send(self.error_reply(error, user_id), ephemeral=True)

    async def apply_meal_change(self, interaction, action, ref, values=None):
        """Confirm button for /edit or /delete: write the change, then show the
        refreshed /today card in place of the confirmation message."""
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
            async with self.user_lock(user_id):
                if action == "delete":
                    await asyncio.to_thread(self.meals.delete, user, ref)
                    self.metrics.incr("meal", "deleted")
                    message = f"🗑️ Deleted {describe_ref(ref)}"
                else:
                    await asyncio.to_thread(self.meals.update, user, ref, values)
                    self.metrics.incr("meal", "edited")
                    lines = changes(ref.__dict__, values)
                    message = f"✏️ Updated **{values['meal_name']}**\n" + "\n".join(
                        f"• {line}" for line in lines)
                reply = await self.replies.after_change(user, message)
            await interaction.edit_original_response(**reply.edit_kwargs(self.summary_view))
        except MealChanged as error:
            await interaction.edit_original_response(
                content=f"⚠️ {error}", embed=None, attachments=[], view=None)
        except Exception as error:
            await interaction.followup.send(self.error_reply(error, user_id), ephemeral=True)

    async def _save_metrics_every_minute(self):
        while True:
            await asyncio.sleep(60)
            await asyncio.to_thread(self.metrics.flush)

    async def close(self):
        if self._metrics_task:
            self._metrics_task.cancel()
        await asyncio.to_thread(self.metrics.flush)
        await super().close()

    def record_ai_attempt(self, model, outcome):
        self.metrics.incr("ai_call", f"{model}:{outcome}")

    async def access_refusal(self, user_id):
        """A refusal message if the user may not use the bot right now, else None."""
        if not await self.membership.is_allowed(user_id):
            self.metrics.incr("refused", "not_member")
            return "🔒 This bot is only available to members of its Discord server."
        if not self.rate_limiter.allow(user_id):
            self.metrics.incr("refused", "rate_limited")
            return "⏳ You're sending messages too quickly. Please wait a minute."
        self.metrics.seen_user(user_id)
        return None

    def user_lock(self, user_id):
        """Serializes one user's requests so two quick messages can't race."""
        return self._user_locks[user_id]

    def error_reply(self, error, user_id):
        """The user-facing message for an error while handling a request."""
        if isinstance(error, ParseError):
            self.metrics.incr("request", "unreadable")
            return f"🤔 {error}\n\n{HELP_TEXT}"
        if isinstance(error, MealNotSaved):
            self.metrics.incr("request", "not_saved")
            logger.error("Could not save a meal for %s", user_id, exc_info=error.__cause__)
            meal = error.parsed
            reason = ("Google Sheets isn't responding" if is_temporary_error(error.__cause__)
                      else "something went wrong saving it to Google Sheets")
            return (f"⚠️ I couldn't save **{meal.meal_name}** ({meal.macros['calories']} kcal): "
                    f"{reason}. Nothing was logged, so please send it again in a few minutes.")
        if is_temporary_error(error):
            self.metrics.incr("request", "sheets_down")
            logger.warning("Google Sheets unavailable for %s: %s", user_id, error)
            return ("📄 Google Sheets isn't responding, so I can't load your meals right now. "
                    "Please try again in a few minutes.")
        if is_daily_quota(error):
            self.metrics.incr("request", "quota_used_up")
            logger.warning("Gemini daily quota used up for %s: %s", user_id, error)
            return ("⏳ Today's free AI limit has been used up. It resets at midnight Pacific "
                    f"({until_quota_reset()} from now). Until then `/today`, `/week`, `/goals`, "
                    "`/edit` and `/delete` still work.")
        if is_overloaded(error):
            self.metrics.incr("request", "all_busy")
            logger.warning("All Gemini models unavailable for %s: %s", user_id, error)
            return "⏳ The AI service is busy right now. Please try again in a minute."
        self.metrics.incr("request", "error")
        logger.exception("Failed to process request for %s", user_id, exc_info=error)
        return "❌ I could not process that message. Please try again."

    async def handle_dm(self, message):
        discord_id = str(message.author.id)
        display_name = message.author.display_name.strip()
        user = await asyncio.to_thread(
            self.user_store.ensure_user, discord_id, display_name
        )
        parsed = await parse_input_with_ai(
            self.ai_client, self.settings.gemini_models, message.content,
            on_attempt=self.record_ai_attempt,
        )
        self.metrics.incr("request", "answered")
        self.metrics.incr("dm", parsed.intent)

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
        try:
            await self._save_meal(user, values)
        except Exception as error:
            raise MealNotSaved(parsed) from error
        self.metrics.incr("meal", "logged")

        source = "AI Estimated" if parsed.is_estimation else "Manual Input"
        logged = (
            f"✅ **Logged!** ({source})\n"
            f"**Meal:** {parsed.meal_name}\n{format_macros(parsed.macros)}"
        )
        user = await asyncio.to_thread(self.user_store.get, discord_id)
        left_today = await self.replies.left_today(user)
        return f"{logged}\n{left_today}" if left_today else logged

    async def _save_meal(self, user, values):
        """Append the meal, retrying brief Sheets errors: Gemini has already been
        paid for, so a hiccup shouldn't lose the meal or cost the user a retry."""
        for delay in (*self.save_retry_delays, None):
            try:
                return await asyncio.to_thread(self._append_meal, user, values)
            except Exception as error:
                if delay is None or not is_temporary_error(error):
                    raise
                logger.warning("Sheets error saving a meal (%s); retrying in %ss", error, delay)
                await asyncio.sleep(delay)

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

    try:
        MacroBot(settings).run(settings.discord_token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        logger.error(
            "Discord refused the Server Members Intent. Turn it on in the Developer "
            "Portal (Bot -> Privileged Gateway Intents) to enable welcome DMs. "
            "Starting without welcome DMs."
        )
        MacroBot(settings, welcome_new_members=False).run(
            settings.discord_token, log_handler=None
        )


if __name__ == "__main__":
    main()
