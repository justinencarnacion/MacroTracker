"""/today, /week, /goals show, and /goals set."""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.macros import GOAL_LIMITS

logger = logging.getLogger(__name__)

# Usable in the bot's DMs and in server channels; installed to servers only.
CONTEXTS = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=False)
INSTALLS = app_commands.AppInstallationType(guild=True, user=False)


class SummaryCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    goals = app_commands.Group(
        name="goals",
        description="View or set your daily macro goals",
        allowed_contexts=CONTEXTS,
        allowed_installs=INSTALLS,
    )

    async def _respond(self, interaction, build_reply):
        """Defer, check access, build the reply, and send it.

        Replies in server channels are visible only to the user who ran the
        command; in DMs they're normal messages.
        """
        private = interaction.guild is not None
        await interaction.response.defer(ephemeral=private, thinking=True)
        user_id = interaction.user.id
        try:
            refusal = await self.bot.access_refusal(user_id)
            if refusal:
                reply = refusal
            else:
                user = await asyncio.to_thread(
                    self.bot.user_store.ensure_user,
                    str(user_id),
                    interaction.user.display_name.strip(),
                )
                async with self.bot.user_lock(user_id):
                    reply = await build_reply(user)
        except Exception as error:
            reply = self.bot.error_reply(error, user_id)
        await interaction.followup.send(reply, ephemeral=private)

    @app_commands.command(name="today", description="What you've eaten today and what's left")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def today(self, interaction: discord.Interaction):
        await self._respond(interaction, self.bot.replies.today)

    @app_commands.command(name="week", description="This week's progress, Monday to Sunday")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def week(self, interaction: discord.Interaction):
        await self._respond(interaction, self.bot.replies.week)

    @goals.command(name="show", description="Show your daily macro goals")
    async def goals_show(self, interaction: discord.Interaction):
        await self._respond(interaction, self.bot.replies.goals)

    @goals.command(name="set", description="Set daily goals (first time: all four; later: any)")
    @app_commands.describe(
        calories="Daily calories (kcal)",
        protein="Daily protein (g)",
        carbs="Daily carbs (g)",
        fat="Daily fat (g)",
    )
    async def goals_set(
        self,
        interaction: discord.Interaction,
        calories: app_commands.Range[int, 1, GOAL_LIMITS["calories"]] = None,
        protein: app_commands.Range[int, 0, GOAL_LIMITS["protein"]] = None,
        carbs: app_commands.Range[int, 0, GOAL_LIMITS["carbs"]] = None,
        fat: app_commands.Range[int, 0, GOAL_LIMITS["fat"]] = None,
    ):
        updates = {"calories": calories, "protein": protein, "carbs": carbs, "fat": fat}
        if all(value is None for value in updates.values()):
            await interaction.response.send_message(
                "Include at least one value, e.g. `/goals set calories:2200`.",
                ephemeral=True,
            )
            return
        await self._respond(
            interaction, lambda user: self.bot.replies.set_goals(user, updates)
        )
