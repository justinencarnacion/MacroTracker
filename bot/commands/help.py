"""/help: the getting-started guide, available anytime."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands.common import respond
from bot.welcome import GUIDE


class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="How to use MacroTracker")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    async def help(self, interaction: discord.Interaction):
        async def build(user):
            return GUIDE

        await respond(self.bot, interaction, build)
