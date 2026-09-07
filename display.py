def prompt_num(text):
    while True:
        val = input(text).strip()
        if not val:
            return 0.0
        try:
            return float(val)
        except ValueError:
            print("Invalid input. Please enter a number.")


def display_dashboard(
    totals, limits, profile_name, title="CURRENT DAILY MACRO STATUS"
):
    print("\n" + "=" * 52)
    print(f"    {title} [{profile_name.upper()}]    ")
    print("=" * 52)

    keys = [
        ("calories", "Calories (kcal)"),
        ("protein", "Protein (g)"),
        ("carbs", "Carbs (g)"),
        ("fat", "Fat (g)"),
    ]

    for key, label in keys:
        used = totals[key]
        limit = limits[key]
        rem = limit - used
        if rem >= 0:
            print(f"{label:<16}: {used:.1f} / {limit} (Remaining: {rem:.1f})")
        else:
            print(
                f"{label:<16}: {used:.1f} / {limit} (⚠️ EXCEEDED BY {abs(rem):.1f}!)"
            )
    print("-" * 52)