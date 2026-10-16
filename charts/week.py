"""This week: daily calories Monday to Sunday against the calorie goal."""

from matplotlib.patches import Rectangle

from charts import theme
from charts.today import TOLERANCE

PLACEHOLDER_HEIGHT = 0.12  # fraction of the goal, for days with nothing logged


def day_color(calories, goal, is_today):
    if is_today:
        return theme.BLURPLE
    if goal > 0 and calories > goal * (1 + TOLERANCE):
        return theme.RED
    return theme.GREEN


def render_week(summary):
    """PNG bytes for a WeekSummary (tracking.summaries)."""
    goal = summary.goals["calories"]
    figure = theme.new_figure(height_in=3.6)
    axes = figure.add_subplot()
    theme.style_axes(axes)

    peak = max([goal] + [day.totals["calories"] for day in summary.days])
    top = peak * 1.18 if peak > 0 else 1
    labels = []
    for index, day in enumerate(summary.days):
        labels.append(f"{day.day.strftime('%a')}\n{day.day.day}")
        calories = day.totals["calories"]
        if day.is_future:
            continue
        if day.meal_count == 0:
            axes.add_patch(Rectangle(
                (index - 0.3, 0), 0.6, goal * PLACEHOLDER_HEIGHT, fill=False,
                edgecolor=theme.MUTED, linestyle=(0, (2, 2)), linewidth=1))
            axes.text(index, goal * PLACEHOLDER_HEIGHT + top * 0.02, "—",
                      ha="center", va="bottom", color=theme.MUTED, fontsize=10)
            continue
        axes.bar(index, calories, width=0.6,
                 color=day_color(calories, goal, day.day == summary.today))
        axes.text(index, calories + top * 0.02, f"{round(calories):,}",
                  ha="center", va="bottom", color=theme.TEXT, fontsize=10)

    if goal > 0:
        axes.axhline(goal, color=theme.MUTED, linestyle=(0, (4, 3)), linewidth=1.2)
        axes.text(6.45, goal, f"goal {round(goal):,}", color=theme.MUTED,
                  fontsize=9, ha="right", va="bottom")
    axes.set_xticks(range(7), labels)
    for index, tick in enumerate(axes.get_xticklabels()):
        day = summary.days[index]
        tick.set_color(theme.TEXT if not day.is_future else theme.FUTURE)
        tick.set_fontweight("bold" if day.day == summary.today else "normal")
    axes.set_yticks([])
    axes.set_xlim(-0.6, 6.6)
    axes.set_ylim(0, top)
    return theme.to_png(figure)
