import asyncio
from collections import defaultdict
from datetime import datetime
import json
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
from core.settings import Settings, SettingsError
from sheets.sheet_manager import connect_sheets, get_worksheet_for_user
from core.user_store import UserStore

logger = logging.getLogger("macrotracker")

DEFAULT_LIMITS = {
    "calories": 2050,
    "protein": 160,
    "carbs": 210,
    "fat": 70,
}

HELP_TEXT = (
    "👋 I'm your macro tracker. DM me things like:\n"
    "• `2 eggs and toast` or `450 cals, 35p, 40c, 12f` — log a meal\n"
    "• `change my goals to 2200 cals, 180p` — update daily goals\n"
    "• `set my timezone to America/New_York` — so meals land on the right day"
)


def worksheet_title(display_name, discord_id):
    """Create a readable, unique Google Sheets worksheet title."""
    safe_name = "".join(
        character for character in display_name if character not in "[]:*?/\\"
    ).strip()
    safe_name = safe_name or "Discord User"
    suffix = f" ({discord_id[-6:]})"
    return f"{safe_name[:100 - len(suffix)]}{suffix}"


def load_legacy_goals(display_name, config_file="cli/config.json"):
    """Goals saved in cli/config.json by the CLI, used until the user sets their own."""
    try:
        with open(config_file, "r") as f:
            profiles = json.load(f).get("profiles", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return profiles.get(display_name, {}).get("daily_limits")


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

    async def setup_hook(self):
        self.spreadsheet = await asyncio.to_thread(
            connect_sheets,
            self.settings.google_credentials,
            self.settings.sheet_name,
            self.settings.sheet_id,
        )
        logger.info("Connected to spreadsheet '%s'", self.spreadsheet.title)

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
            if not await self.membership.is_allowed(user_id):
                await message.channel.send(
                    "🔒 This bot is only available to members of its Discord server."
                )
                return
            if not self.rate_limiter.allow(user_id):
                await message.channel.send(
                    "⏳ You're sending messages too quickly. Please wait a minute."
                )
                return

            async with self._user_locks[user_id], message.channel.typing():
                reply = await self.handle_dm(message)
        except ParseError as error:
            reply = f"🤔 {error}\n\n{HELP_TEXT}"
        except Exception as error:
            if is_overloaded(error):
                logger.warning("All Gemini models unavailable for %s: %s", user_id, error)
                reply = "⏳ The AI service is busy right now. Please try again in a minute."
            else:
                logger.exception("Failed to process Discord message for %s", user_id)
                reply = "❌ I could not process that message. Please try again."
        await message.channel.send(reply)

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
            goals = {**self.goals_for(user), **parsed.macros}
            await asyncio.to_thread(self.user_store.set_goals, discord_id, goals)
            return f"🎯 **Updated daily goals for {display_name}!**\n{format_macros(goals)}"

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
        return (
            f"✅ **Logged to your Google Sheet tab!** ({source})\n"
            f"**Meal:** {parsed.meal_name}\n{format_macros(parsed.macros)}"
        )

    def goals_for(self, user):
        return dict(
            user["goals"]
            or load_legacy_goals(user["display_name"])
            or DEFAULT_LIMITS
        )

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
