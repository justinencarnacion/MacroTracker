"""Shared plumbing for slash commands."""

import asyncio

from discord import app_commands

from bot.replies import Reply

# Usable in the bot's DMs and in server channels; installed to servers only.
CONTEXTS = app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=False)
INSTALLS = app_commands.AppInstallationType(guild=True, user=False)


async def respond(bot, interaction, build_reply):
    """Defer, check access, build the reply for this user, and send it.

    Replies in server channels are visible only to the user who ran the
    command; in DMs they're normal messages.
    """
    private = interaction.guild is not None
    await interaction.response.defer(ephemeral=private, thinking=True)
    user_id = interaction.user.id
    try:
        refusal = await bot.access_refusal(user_id)
        if refusal:
            reply = refusal
        else:
            user = await asyncio.to_thread(
                bot.user_store.ensure_user,
                str(user_id),
                interaction.user.display_name.strip(),
            )
            async with bot.user_lock(user_id):
                reply = await build_reply(user)
    except Exception as error:
        reply = bot.error_reply(error, user_id)
    await interaction.followup.send(
        **Reply.of(reply).send_kwargs(bot.summary_view), ephemeral=private
    )
