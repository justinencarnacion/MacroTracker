"""Colors and sizing matched to Discord's dark theme."""

import io

from matplotlib.figure import Figure

BACKGROUND = "#2b2d31"  # Discord dark embed background
TRACK = "#3f4147"  # unfilled part of a bar, gridlines
TEXT = "#f2f3f5"
MUTED = "#949ba4"
FUTURE = "#6d6f78"  # labels for days that haven't happened yet
BLURPLE = "#5865f2"  # in progress / today
GREEN = "#23a55a"  # on target
RED = "#f23f43"  # over the goal

WIDTH_IN = 8.0
DPI = 150  # crisp on high-density phone screens; files stay well under Discord limits


def new_figure(height_in):
    """A figure with the theme background. Uses Figure directly (not pyplot),
    so charts can be drawn safely from worker threads."""
    figure = Figure(figsize=(WIDTH_IN, height_in), dpi=DPI, facecolor=BACKGROUND)
    return figure


def style_axes(axes):
    axes.set_facecolor(BACKGROUND)
    for spine in axes.spines.values():
        spine.set_visible(False)
    axes.tick_params(colors=MUTED, length=0, labelsize=10)


def to_png(figure):
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", facecolor=figure.get_facecolor(),
                   bbox_inches="tight", pad_inches=0.25)
    return buffer.getvalue()
