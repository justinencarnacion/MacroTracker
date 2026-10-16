"""Discord embed cards for /today and /week, with the chart attached as an image."""

import discord

from bot import formatting
from core.macros import MACRO_KEYS, MACRO_LABELS

COLOR = 0x5865F2  # Discord blurple, matches the charts
DESCRIPTION_BUDGET = 3500  # embed descriptions allow 4096; leave headroom
TODAY_IMAGE = "today.png"
WEEK_IMAGE = "week.png"


def _progress_field(key, eaten, goal, left):
    unit = formatting.unit(key)
    return (f"{formatting.amount(eaten)} / {formatting.amount(goal)}{unit}\n"
            f"{formatting.left_or_over(left, key)}")


def today_embed(summary):
    embed = discord.Embed(
        title=formatting.day_title(summary.day),
        description=formatting.numbered_meals(summary.meals, DESCRIPTION_BUDGET),
        color=COLOR,
    )
    for key in MACRO_KEYS:
        embed.add_field(
            name=MACRO_LABELS[key],
            value=_progress_field(key, summary.totals[key], summary.goals[key],
                                  summary.remaining[key]),
            inline=True,
        )
    embed.set_image(url=f"attachment://{TODAY_IMAGE}")
    return embed


def week_embed(summary):
    embed = discord.Embed(
        title=formatting.week_title(summary),
        description=(f"Day {summary.days_elapsed} of 7 · week so far vs "
                     f"{formatting.days_so_far(summary)}\n{formatting.week_table(summary)}"),
        color=COLOR,
    )
    for key in MACRO_KEYS:
        embed.add_field(
            name=MACRO_LABELS[key],
            value=_progress_field(key, summary.totals[key], summary.target[key],
                                  summary.remaining[key]),
            inline=True,
        )
    embed.add_field(name="Daily average", value=formatting.macro_line(summary.daily_average),
                    inline=False)
    embed.set_image(url=f"attachment://{WEEK_IMAGE}")
    return embed
