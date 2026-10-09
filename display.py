MACRO_LABELS = [
    ("calories", "Calories (kcal)"),
    ("protein", "Protein (g)"),
    ("carbs", "Carbs (g)"),
    ("fat", "Fat (g)"),
]


def prompt_num(text):
    while True:
        val = input(text).strip()
        if not val:
            return 0.0
        try:
            return float(val)
        except ValueError:
            print("Invalid input. Please enter a number.")


def remaining_status(used, limit):
    """Describe what is left of a daily limit, or how far past it the user is."""
    rem = limit - used
    if rem >= 0:
        return f"Remaining: {rem:.1f}"
    return f"⚠️ EXCEEDED BY {abs(rem):.1f}!"


def display_dashboard(
    totals, limits, profile_name, title="CURRENT DAILY MACRO STATUS"
):
    print("\n" + "=" * 52)
    print(f"    {title} [{profile_name.upper()}]    ")
    print("=" * 52)

    for key, label in MACRO_LABELS:
        used = totals[key]
        limit = limits[key]
        print(
            f"{label:<16}: {used:.1f} / {limit} ({remaining_status(used, limit)})"
        )
    print("-" * 52)


def format_dashboard_discord(totals, limits, title="Today's Totals"):
    """Render the same daily dashboard as display_dashboard, as Discord markdown."""
    lines = [f"📊 **{title}**"]
    for key, label in MACRO_LABELS:
        used = totals[key]
        limit = limits[key]
        lines.append(
            f"**{label}:** {used:.1f} / {limit} ({remaining_status(used, limit)})"
        )
    return "\n".join(lines)
