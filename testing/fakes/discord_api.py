"""Stand-ins for the Discord objects the bot receives: users, DM messages, slash
command and button interactions, and the server membership lookup.

Everything the bot sends is recorded as a `Sent` in the user's inbox instead
of going to Discord. Interactions enforce Discord's rules (answer within 3
seconds, answer only once, follow up only after answering) by raising the same
errors Discord would, so a bot bug that would fail live fails here too.
"""

import contextlib
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import discord

INTERACTION_DEADLINE = 3.0  # seconds Discord allows before an interaction expires


def http_error(error_class, status, reason, message):
    return error_class(SimpleNamespace(status=status, reason=reason), message)


@dataclass
class Sent:
    """One thing the bot showed the user.

    via: "dm" (a DM message), "reply" (an interaction's first response),
    "followup", "edit" (an existing message changed in place), or "modal".
    """

    via: str
    content: str | None = None
    embed: discord.Embed | None = None
    image: bool = False
    view: discord.ui.View | None = None
    modal: discord.ui.Modal | None = None
    ephemeral: bool = False
    at: float = field(default_factory=time.monotonic)

    @property
    def text(self):
        """Everything readable: content plus the embed's title, text, and fields."""
        parts = [self.content or ""]
        if self.embed is not None:
            parts += [self.embed.title or "", self.embed.description or ""]
            parts += [f"{f.name} {f.value}" for f in self.embed.fields]
        return "\n".join(part for part in parts if part)

    def labels(self):
        """Labels of the buttons under this message."""
        if self.view is None:
            return []
        return [item.label for item in self.view.children if isinstance(item, discord.ui.Button)]


def _sent(via, kwargs, ephemeral=False):
    attachments = kwargs.get("attachments") or []
    return Sent(
        via=via,
        content=kwargs.get("content"),
        embed=kwargs.get("embed"),
        image=kwargs.get("file") is not None or bool(attachments),
        view=kwargs.get("view"),
        ephemeral=ephemeral,
    )


class FakeUser:
    """A Discord user, and a server member when they've joined."""

    def __init__(self, user_id, name, guild_id=None, accepts_dms=True, is_bot=False):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.global_name = name
        self.bot = is_bot
        self.guild = SimpleNamespace(id=guild_id)
        self.accepts_dms = accepts_dms
        self.inbox = []

    @property
    def mention(self):
        return f"<@{self.id}>"

    async def send(self, content=None, **kwargs):
        """The bot DMing this user directly (e.g. the welcome guide)."""
        if not self.accepts_dms:
            raise http_error(discord.Forbidden, 403, "Forbidden",
                             "Cannot send messages to this user")
        self.inbox.append(_sent("dm", {"content": content, **kwargs}))


class FakeDMChannel(discord.DMChannel):
    """A DM with the bot. Subclasses the real class so the bot's
    `isinstance(channel, discord.DMChannel)` check passes."""

    def __init__(self, user):  # deliberately skips the real __init__
        self.id = user.id
        self._user = user

    async def send(self, content=None, **kwargs):
        self._user.inbox.append(_sent("dm", {"content": content, **kwargs}))

    def typing(self):
        return contextlib.nullcontext()


class FakeMessage:
    def __init__(self, user, content):
        self.author = user
        self.content = content
        self.channel = FakeDMChannel(user)
        self.guild = None


class FakeInteraction:
    """A slash command, button press, menu choice, or form submission."""

    def __init__(self, user, command_name=None, guild=None):
        self.user = user
        self.guild = guild
        self.command = SimpleNamespace(qualified_name=command_name) if command_name else None
        self.created = time.monotonic()
        self.response = FakeResponse(self)
        self.followup = FakeFollowup(self)

    def _record(self, sent):
        self.user.inbox.append(sent)

    async def edit_original_response(self, **kwargs):
        if not self.response.is_done():
            raise http_error(discord.NotFound, 404, "Not Found", "Unknown Webhook")
        self._record(_sent("edit", kwargs))


class FakeResponse:
    def __init__(self, interaction):
        self._interaction = interaction
        self._done = False
        self.deferred_ephemeral = False

    def is_done(self):
        return self._done

    def _respond(self):
        if self._done:
            raise discord.InteractionResponded(self._interaction)
        if time.monotonic() - self._interaction.created > INTERACTION_DEADLINE:
            raise http_error(discord.NotFound, 404, "Not Found", "Unknown interaction")
        self._done = True

    async def defer(self, *, ephemeral=False, thinking=False):
        self._respond()
        self.deferred_ephemeral = ephemeral

    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        self._respond()
        self._interaction._record(_sent("reply", {"content": content, **kwargs}, ephemeral))

    async def edit_message(self, **kwargs):
        self._respond()
        self._interaction._record(_sent("edit", kwargs))

    async def send_modal(self, modal):
        self._respond()
        self._interaction._record(Sent(via="modal", modal=modal))


class FakeFollowup:
    def __init__(self, interaction):
        self._interaction = interaction

    async def send(self, content=None, *, ephemeral=False, **kwargs):
        if not self._interaction.response.is_done():
            raise http_error(discord.NotFound, 404, "Not Found", "Unknown Webhook")
        self._interaction._record(_sent("followup", {"content": content, **kwargs}, ephemeral))


class FakeGuild:
    def __init__(self, guild_id, member_ids):
        self.id = guild_id
        self._member_ids = member_ids

    async def fetch_member(self, user_id):
        if user_id not in self._member_ids:
            raise http_error(discord.NotFound, 404, "Not Found", "Unknown Member")
        return SimpleNamespace(id=user_id)


class FakeGuildLookup:
    """What GuildMembershipChecker needs from the bot: finding the server.
    `member_ids` is shared, so adding an ID makes that user a member."""

    def __init__(self, guild_id, member_ids):
        self.guild = FakeGuild(guild_id, member_ids)
        self.lookups = 0

    def get_guild(self, guild_id):
        return None  # not cached, as when the bot can't see the server yet

    async def fetch_guild(self, guild_id):
        self.lookups += 1
        return self.guild
