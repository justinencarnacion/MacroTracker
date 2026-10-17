"""Meal picker, edit form, and Yes/No confirmation for /edit and /delete.

Only the person who ran the command can use these controls. Nothing is
written to the sheet until the user presses the confirm button.
"""

import dataclasses

import discord

from bot import formatting
from core.macros import MACRO_KEYS, MACRO_LABELS
from tracking.meal_service import InvalidMeal, MealRef, parse_meal_edit

OPTION_LIMIT = 25  # Discord's maximum options in one dropdown
TIMEOUT_SECONDS = 180


def _clip(text, limit=100):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def meal_option(index, meal):
    when = formatting.meal_when(meal)
    return discord.SelectOption(
        label=_clip(f"{when} · {meal['meal_name']}"),
        description=_clip(formatting.macro_line(meal)),
        value=str(index),
    )


def changes(meal, values):
    """Lines like 'Calories: 980 → 900' for fields that differ."""
    lines = []
    if values["meal_name"] != meal["meal_name"]:
        lines.append(f"Name: {meal['meal_name']} → {values['meal_name']}")
    for key in MACRO_KEYS:
        if round(float(values[key]), 2) != round(float(meal[key]), 2):
            unit = formatting.unit(key)
            lines.append(f"{MACRO_LABELS[key]}: {formatting.amount(meal[key])}{unit} → "
                         f"{formatting.amount(values[key])}{unit}")
    return lines


class OwnerOnlyView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=TIMEOUT_SECONDS)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This menu belongs to someone else. Run the command yourself.", ephemeral=True)
            return False
        return True


class ConfirmView(OwnerOnlyView):
    def __init__(self, owner_id, confirm_label, confirm_style, on_confirm):
        super().__init__(owner_id)
        self.on_confirm = on_confirm
        self.confirm_button.label = confirm_label
        self.confirm_button.style = confirm_style

    @discord.ui.button(label="Confirm")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await self.on_confirm(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="Cancelled. Nothing was changed.", embed=None, attachments=[], view=None)


class MealPicker(OwnerOnlyView):
    def __init__(self, bot, owner_id, mode, meals):
        super().__init__(owner_id)
        self.bot = bot
        self.mode = mode  # "edit" or "delete"
        self.meals = meals[:OPTION_LIMIT]
        self.select = discord.ui.Select(
            placeholder=f"Choose a meal to {mode}",
            options=[meal_option(index, meal) for index, meal in enumerate(self.meals)],
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        meal = self.meals[int(self.select.values[0])]
        ref = MealRef.from_meal(meal)
        self.stop()
        if self.mode == "delete":
            view = ConfirmView(
                self.owner_id, "Delete", discord.ButtonStyle.danger,
                lambda confirm: self.bot.apply_meal_change(confirm, "delete", ref),
            )
            await interaction.response.edit_message(
                content=f"🗑️ Delete {formatting.meal_summary(meal)}?", view=view)
        else:
            await interaction.response.send_modal(MealEditModal(self.bot, self.owner_id, meal, ref))


class MealEditModal(discord.ui.Modal, title="Edit meal"):
    def __init__(self, bot, owner_id, meal, ref):
        super().__init__(timeout=TIMEOUT_SECONDS)
        self.bot = bot
        self.owner_id = owner_id
        self.meal = meal
        self.ref = ref
        self.name_input = discord.ui.TextInput(
            label="Meal name", default=meal["meal_name"][:100], max_length=100)
        self.add_item(self.name_input)
        self.inputs = {}
        for key in MACRO_KEYS:
            text_input = discord.ui.TextInput(
                label=f"{MACRO_LABELS[key]} ({formatting.unit(key).strip()})",
                default=formatting.amount(meal[key]).replace(",", ""), max_length=8)
            self.inputs[key] = text_input
            self.add_item(text_input)

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.owner_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            values = parse_meal_edit(
                self.name_input.value,
                {key: text_input.value for key, text_input in self.inputs.items()},
            )
        except InvalidMeal as error:
            await interaction.response.send_message(
                f"🤔 {error} Nothing was changed; run `/edit` to try again.", ephemeral=True)
            return
        lines = changes(self.meal, values)
        if not lines:
            await interaction.response.edit_message(
                content="No changes, so nothing was saved.", view=None)
            return
        view = ConfirmView(
            self.owner_id, "Save", discord.ButtonStyle.success,
            lambda confirm: self.bot.apply_meal_change(confirm, "edit", self.ref, values),
        )
        await interaction.response.edit_message(
            content=(f"✏️ Save these changes to {formatting.meal_summary(self.meal)}?\n"
                     + "\n".join(f"• {line}" for line in lines)),
            view=view,
        )


def describe_ref(ref):
    return formatting.meal_summary(dataclasses.asdict(ref))
