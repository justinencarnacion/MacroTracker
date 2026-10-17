"""/edit and /delete: fix a meal from the last 7 days."""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands.common import respond
from bot.replies import Reply
from bot.views.meals import OPTION_LIMIT, MealPicker
from tracking.meal_service import RECENT_DAYS


class MealCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _picker(self, interaction, mode):
        async def build(user):
            meals = await asyncio.to_thread(self.bot.meals.recent_meals, user)
            if not meals:
                return f"No meals logged in the last {RECENT_DAYS} days."
            note = (f" Showing the {OPTION_LIMIT} most recent."
                    if len(meals) > OPTION_LIMIT else "")
            return Reply(
                content=f"Which meal do you want to {mode}? (last {RECENT_DAYS} days, newest first){note}",
                view=MealPicker(self.bot, interaction.user.id, mode, meals),
            )

        await respond(self.bot, interaction, build)

    @app_commands.command(name="edit", description="Edit a meal from the last 7 days")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def edit(self, interaction: discord.Interaction):
        await self._picker(interaction, "edit")

    @app_commands.command(name="delete", description="Delete a meal from the last 7 days")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def delete(self, interaction: discord.Interaction):
        await self._picker(interaction, "delete")
