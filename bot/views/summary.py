"""[Today] [Week] buttons under summary cards.

The buttons have fixed custom IDs and no timeout, and one instance is
registered with the bot at startup, so buttons on old messages keep working
after the bot restarts. Pressing a button shows the presser's own data.
"""

import discord

TODAY_ID = "macrotracker:summary:today"
WEEK_ID = "macrotracker:summary:week"


class SummaryView(discord.ui.View):
    def __init__(self, bot, current=None):
        super().__init__(timeout=None)
        self.bot = bot
        for button, kind in ((self.today_button, "today"), (self.week_button, "week")):
            selected = kind == current
            button.style = discord.ButtonStyle.primary if selected else discord.ButtonStyle.secondary
            button.disabled = selected

    @discord.ui.button(label="Today", emoji="📅", custom_id=TODAY_ID)
    async def today_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.switch_summary(interaction, "today")

    @discord.ui.button(label="Week", emoji="📊", custom_id=WEEK_ID)
    async def week_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.switch_summary(interaction, "week")
