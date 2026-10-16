"""Today: one horizontal progress bar per macro, filled toward the daily goal.

The grey track ends at the goal. Anything eaten beyond the goal is drawn as an
overflow segment past the end of the track (capped so the chart stays readable).
"""

from charts import theme
from core.macros import MACRO_KEYS, MACRO_LABELS

MAX_FRACTION = 1.3  # overflow is drawn up to 130% of the goal
TOLERANCE = 0.05  # within 5% over the goal still counts as on target


def bar_color(key, eaten, goal):
    """Protein is a minimum (reaching it is good); the others are limits."""
    if goal <= 0:
        return theme.MUTED
    fraction = eaten / goal
    if key == "protein":
        return theme.GREEN if fraction >= 1 else theme.BLURPLE
    if fraction > 1 + TOLERANCE:
        return theme.RED
    if fraction >= 1 - TOLERANCE:
        return theme.GREEN
    return theme.BLURPLE


def bar_label(key, eaten, goal):
    unit = " kcal" if key == "calories" else "g"
    percent = f" · {round(100 * eaten / goal)}%" if goal > 0 else ""
    return f"{round(eaten):,} / {round(goal):,}{unit}{percent}"


def render_today(summary):
    """PNG bytes for a DaySummary (tracking.summaries)."""
    figure = theme.new_figure(height_in=3.0)
    axes = figure.add_subplot()
    theme.style_axes(axes)

    keys = list(reversed(MACRO_KEYS))  # calories at the top
    for row, key in enumerate(keys):
        eaten, goal = summary.totals[key], summary.goals[key]
        fraction = eaten / goal if goal > 0 else 0
        color = bar_color(key, eaten, goal)
        axes.barh(row, 1.0, height=0.55, color=theme.TRACK)
        axes.barh(row, min(fraction, 1.0), height=0.55, color=color)
        if fraction > 1:
            axes.barh(row, min(fraction, MAX_FRACTION) - 1.0, left=1.0, height=0.55,
                      color=color, alpha=0.65)
        axes.text(max(min(fraction, MAX_FRACTION), 1.0) + 0.03, row,
                  bar_label(key, eaten, goal), va="center", ha="left",
                  color=theme.TEXT, fontsize=11)

    axes.set_yticks(range(len(keys)), [MACRO_LABELS[key] for key in keys],
                    color=theme.TEXT, fontsize=12)
    axes.set_xticks([])
    axes.set_xlim(0, MAX_FRACTION + 0.75)
    axes.set_ylim(-0.6, len(keys) - 0.4)
    return theme.to_png(figure)
