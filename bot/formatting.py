"""Turns tracking summaries into Discord message text. No I/O."""

from core.macros import MACRO_KEYS, MACRO_LABELS, MACRO_TAGS

DISCORD_LIMIT = 2000
MAX_LISTED_MEALS = 20
BAR_WIDTH = 10

NEEDS_GOALS_TEXT = (
    "🎯 Set your daily goals first, then I can show your progress:\n"
    "• `/goals set calories:2200 protein:180 carbs:220 fat:70`\n"
    "• or DM me `set my goals to 2200 cals, 180p, 220c, 70f`"
)
SET_GOALS_HINT = "🎯 Set your goals (`/goals set`) to see what's left today."


def amount(value):
    """1640.0 -> '1,640'; 12.5 -> '12.5'."""
    rounded = round(value, 1)
    return f"{rounded:,.0f}" if float(rounded).is_integer() else f"{rounded:,.1f}"


def unit(key):
    return " kcal" if key == "calories" else "g"


def progress_bar(value, goal, width=BAR_WIDTH):
    if goal <= 0:
        return "░" * width
    filled = max(0, min(width, round(width * value / goal)))
    return "█" * filled + "░" * (width - filled)


def left_or_over(left, key):
    if left >= 0:
        return f"{amount(left)}{unit(key)} left"
    return f"{amount(-left)}{unit(key)} over"


def progress_block(totals, goals, remaining):
    """A monospace block of progress bars, one line per macro."""
    lines = []
    for key in MACRO_KEYS:
        lines.append(
            f"{MACRO_LABELS[key]:<8} {progress_bar(totals[key], goals[key])} "
            f"{amount(totals[key]):>6} / {amount(goals[key]):<7} {left_or_over(remaining[key], key)}"
        )
    return "```\n" + "\n".join(lines) + "\n```"


def macro_line(values):
    """'220 kcal · P 15g · C 16g · F 11g'"""
    return (
        f"{amount(values['calories'])} kcal · P {amount(values['protein'])}g · "
        f"C {amount(values['carbs'])}g · F {amount(values['fat'])}g"
    )


def meal_line(number, meal):
    time = str(meal["date_time"])[11:16]
    return f"{number}. `{time}` {meal['meal_name']} — {macro_line(meal)}"


def _fit(text):
    if len(text) <= DISCORD_LIMIT:
        return text
    return text[: DISCORD_LIMIT - 2] + "…"


def format_day(summary):
    header = f"📅 **Today · {summary.day.strftime('%a, %b')} {summary.day.day}**"
    progress = (
        "\n\n**Progress**\n"
        f"{progress_block(summary.totals, summary.goals, summary.remaining)}"
    )
    if not summary.meals:
        return _fit(f"{header}\nNothing logged yet today.{progress}")

    # List as many meals as fit, always leaving room for the progress section.
    budget = DISCORD_LIMIT - len(header) - len(progress) - len("\n…and 999 more") - 1
    lines = []
    for number, meal in enumerate(summary.meals[:MAX_LISTED_MEALS], start=1):
        line = meal_line(number, meal)
        if sum(len(existing) + 1 for existing in lines) + len(line) + 1 > budget:
            break
        lines.append(line)
    hidden = len(summary.meals) - len(lines)
    if hidden:
        lines.append(f"…and {hidden} more")
    return _fit(f"{header}\n" + "\n".join(lines) + progress)


def format_week(summary):
    start, end = summary.start, summary.end
    header = (
        f"📊 **This week · {start.strftime('%a %b')} {start.day} – "
        f"{end.strftime('%a %b')} {end.day}** (day {summary.days_elapsed} of 7)"
    )
    rows = [f"{'Day':<7}{'kcal':>7}{'P':>6}{'C':>6}{'F':>6}"]
    for day in summary.days:
        label = f"{day.day.strftime('%a')} {day.day.day:<2}"
        if day.is_future:
            rows.append(f"{label:<7}{'·':>7}")
        elif day.meal_count == 0:
            rows.append(f"{label:<7}{'—':>7}")
        else:
            totals = day.totals
            rows.append(
                f"{label:<7}{amount(totals['calories']):>7}{amount(totals['protein']):>6}"
                f"{amount(totals['carbs']):>6}{amount(totals['fat']):>6}"
            )
    days_word = "day" if summary.days_elapsed == 1 else "days"
    return _fit(
        f"{header}\n```\n" + "\n".join(rows) + "\n```\n"
        f"**Week so far** (daily goals × {summary.days_elapsed} {days_word})\n"
        f"{progress_block(summary.totals, summary.target, summary.remaining)}\n"
        f"**Daily average:** {macro_line(summary.daily_average)}"
    )


def format_goals(goals):
    lines = [f"• **{MACRO_LABELS[key]}:** {amount(goals[key])}{unit(key)}" for key in MACRO_KEYS]
    return "🎯 **Your daily goals**\n" + "\n".join(lines)


def format_goals_updated(goals):
    return "✅ **Goals updated!**\n" + format_goals(goals).split("\n", 1)[1]


def format_left_today(remaining):
    """'📉 Left today: 410 kcal · P 64g · C 30g · F 15g over'"""
    parts = []
    for key in MACRO_KEYS:
        left = remaining[key]
        if key == "calories":
            text = f"{amount(abs(left))} kcal"
        else:
            text = f"{MACRO_TAGS[key]} {amount(abs(left))}g"
        parts.append(text if left >= 0 else f"{text} over")
    return "📉 **Left today:** " + " · ".join(parts)
