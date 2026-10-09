from display import format_dashboard_discord

MACRO_KEYS = ("calories", "protein", "carbs", "fat")


def worksheet_title(display_name, discord_id):
    """Create a readable, unique Google Sheets worksheet title."""
    safe_name = "".join(
        character for character in display_name if character not in "[]:*?/\\"
    ).strip()
    safe_name = safe_name or "Discord User"
    suffix = f" ({discord_id[-6:]})"
    return f"{safe_name[:100 - len(suffix)]}{suffix}"


def parse_macros(parsed):
    """Pull the four macros out of the AI response as numbers (missing -> 0)."""
    macros = {}
    for key in MACRO_KEYS:
        try:
            macros[key] = float(parsed.get(key) or 0)
        except (TypeError, ValueError):
            macros[key] = 0.0
    return macros


def add_totals(totals, macros):
    return {key: totals[key] + macros[key] for key in MACRO_KEYS}


def format_number(value):
    return f"{value:g}"


def format_meal_logged(meal_name, macros, is_estimation, tab_title, totals, limits):
    """Confirmation for a logged meal, followed by today's totals vs goals."""
    est_tag = " (AI Estimated)" if is_estimation else " (Manual Input)"
    return (
        f"✅ **Logged to your Google Sheet tab [{tab_title}]!**{est_tag}\n"
        f"**Meal:** {meal_name}\n"
        f"**Calories:** {format_number(macros['calories'])} kcal | "
        f"**P:** {format_number(macros['protein'])}g | "
        f"**C:** {format_number(macros['carbs'])}g | "
        f"**F:** {format_number(macros['fat'])}g\n\n"
        + format_dashboard_discord(totals, limits, title="Today's Totals")
    )
