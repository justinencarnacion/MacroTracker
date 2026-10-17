"""/today, /week, /goals show, and /goals set."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands.common import CONTEXTS, INSTALLS, respond
from core.macros import GOAL_LIMITS


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
        await respond(self.bot, interaction, build_reply)

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
