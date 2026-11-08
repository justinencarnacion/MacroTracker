"""Runs the real MacroBot in-process against fake Discord, Gemini, and Sheets.

    async with Harness() as harness:
        alice = harness.user("Alice")
        await alice.dm("set my goals to 2200 cals, 180p, 220c, 70f")
        await alice.dm("2 eggs and toast")
        card = await alice.slash("today")
        week = await alice.press(card, "Week")

Every request goes through the bot's own code (access checks, per-user locks,
the AI parser and its fallbacks, Sheets reads and writes, charts, replies);
only the network edges are fake. Each action's response time is recorded in
`harness.timings` for the load test.
"""

import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import discord

from bot.access import GuildMembershipChecker
from bot.bot import MacroBot
from bot.commands.help import HelpCommands
from bot.commands.meals import MealCommands
from bot.commands.summaries import SummaryCommands
from core.settings import Settings
from core.user_store import UserStore
from testing.fakes.discord_api import FakeGuildLookup, FakeInteraction, FakeMessage, FakeUser
from testing.fakes.gemini import FakeGemini
from testing.fakes.spreadsheet import FakeSpreadsheet

GUILD_ID = 4242
MODELS = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite")
SERVER = discord.Object(id=GUILD_ID)  # where a slash command run "in the server" comes from

# Slash command name -> (cog attribute holding the cog, command attribute).
COMMANDS = {
    "today": ("summary_cog", "today"),
    "week": ("summary_cog", "week"),
    "goals show": ("summary_cog", "goals_show"),
    "goals set": ("summary_cog", "goals_set"),
    "edit": ("meal_cog", "edit"),
    "delete": ("meal_cog", "delete"),
    "help": ("help_cog", "help"),
}


@dataclass
class Timing:
    action: str  # "dm", "/today", "press Week", ...
    user_id: int
    seconds: float


class Harness:
    """gemini, sheets: fakes to use (new fast ones by default).
    rate_limit: (messages, seconds) per user, as in production by default."""

    def __init__(self, gemini=None, sheets=None, rate_limit=(10, 60),
                 timezone="America/Los_Angeles"):
        self.gemini = gemini or FakeGemini()
        self.sheets = sheets or FakeSpreadsheet()
        self.rate_limit = rate_limit
        self.timezone = timezone
        self.member_ids = set()
        self.timings = []
        self._next_user_id = 100_000_000_000_000_001
        self._tempdir = None
        self.bot = None

    async def __aenter__(self):
        self._tempdir = tempfile.TemporaryDirectory(prefix="macrotracker-sim-")
        settings = Settings(
            discord_token="simulated",
            gemini_api_key="simulated",
            gemini_models=MODELS,
            google_credentials={},
            sheet_name=FakeSpreadsheet.title,
            sheet_id=None,
            default_timezone=self.timezone,
            allowed_guild_id=GUILD_ID,
            rate_limit_count=self.rate_limit[0],
            rate_limit_seconds=self.rate_limit[1],
        )
        self.bot = MacroBot(
            settings,
            ai_client=self.gemini,
            user_store=UserStore(Path(self._tempdir.name) / "users.db"),
            spreadsheet=self.sheets,
        )
        self.guild_lookup = FakeGuildLookup(GUILD_ID, self.member_ids)
        self.bot.membership = GuildMembershipChecker(self.guild_lookup, GUILD_ID)
        await self.bot.connect_services()
        self.summary_cog = SummaryCommands(self.bot)
        self.meal_cog = MealCommands(self.bot)
        self.help_cog = HelpCommands(self.bot)
        return self

    async def __aexit__(self, *exc_info):
        self.bot.metrics.flush()
        self._tempdir.cleanup()

    def user(self, name, member=True, accepts_dms=True):
        """A new simulated person; `member=False` means not in the server."""
        user = FakeUser(self._next_user_id, name, GUILD_ID, accepts_dms)
        self._next_user_id += 1
        if member:
            self.member_ids.add(user.id)
        return SimUser(self, user)

    def record(self, action, user_id, started):
        self.timings.append(Timing(action, user_id, time.monotonic() - started))


class SimUser:
    """One simulated person. Each action returns the last thing the bot showed
    them in response (a `Sent`), or None if the bot showed nothing."""

    def __init__(self, harness, user):
        self.harness = harness
        self.user = user

    @property
    def id(self):
        return self.user.id

    @property
    def inbox(self):
        return self.user.inbox

    async def _run(self, action, coroutine):
        before = len(self.inbox)
        started = time.monotonic()
        await coroutine
        self.harness.record(action, self.id, started)
        new = self.inbox[before:]
        return new[-1] if new else None

    async def join(self):
        """Join the server, which triggers the welcome DM."""
        self.harness.member_ids.add(self.id)
        return await self._run("join", self.harness.bot.on_member_join(self.user))

    async def dm(self, text):
        return await self._run("dm", self.harness.bot.on_message(FakeMessage(self.user, text)))

    async def slash(self, name, in_server=False, **options):
        """Run a slash command, in DMs or (in_server=True) in a server channel."""
        cog_name, attribute = COMMANDS[name]
        cog = getattr(self.harness, cog_name)
        command = getattr(cog, attribute)
        interaction = FakeInteraction(self.user, name, guild=SERVER if in_server else None)
        return await self._run(f"/{name}", command.callback(cog, interaction, **options))

    async def press(self, sent, label):
        """Press the button with this label under a message the bot sent."""
        view = sent.view
        button = next((item for item in view.children
                       if isinstance(item, discord.ui.Button) and item.label == label), None)
        if button is None:
            raise AssertionError(f"No {label!r} button; buttons are {sent.labels()}")
        return await self._run(f"press {label}", self._interact(view, button.callback))

    async def choose(self, sent, index=0):
        """Pick option `index` in the dropdown under a message the bot sent."""
        view = sent.view
        select = next(item for item in view.children if isinstance(item, discord.ui.Select))
        select._values = [select.options[index].value]
        return await self._run("choose", self._interact(view, select.callback))

    async def submit(self, sent, **fields):
        """Fill in and submit a form, e.g. submit(form, calories="900").
        Fields are matched to input labels: meal_name -> "Meal name"."""
        modal = sent.modal
        for key, value in fields.items():
            wanted = key.replace("_", " ").lower()
            with warnings.catch_warnings():  # discord.py 2.7 deprecates reading .label
                warnings.simplefilter("ignore", DeprecationWarning)
                text_input = next(item for item in modal.children
                                  if item.label.lower().startswith(wanted))
            text_input._value = str(value)
        interaction = FakeInteraction(self.user)

        async def run():
            if await modal.interaction_check(interaction):
                await modal.on_submit(interaction)

        return await self._run("submit", run())

    async def _interact(self, view, callback):
        # Discord runs the view's interaction_check before any of its callbacks.
        interaction = FakeInteraction(self.user)
        if await view.interaction_check(interaction):
            await callback(interaction)
