from datetime import datetime
import json
import os
import sys
import gspread

CONFIG_FILE = "config.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: '{CONFIG_FILE}' not found in current directory.")
        sys.exit(1)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def connect_sheets(config):
    try:
        gc = gspread.service_account(filename=config["credentials_file"])
        spreadsheet = gc.open(config["google_sheet_name"])
        return spreadsheet
    except Exception as e:
        print(f"\n[Connection Error]: {e}")
        print(
            "Check credentials.json and ensure your sheet is shared with the service account email."
        )
        sys.exit(1)


def get_or_create_worksheet(spreadsheet, profile_name):
    """Fetch existing tab for profile or create a new one."""
    try:
        sheet = spreadsheet.worksheet(profile_name)
    except gspread.exceptions.WorksheetNotFound:
        print(
            f"\nCreating new dedicated worksheet tab for profile: '{profile_name}'..."
        )
        sheet = spreadsheet.add_worksheet(
            title=profile_name, rows="1000", cols="10"
        )
    ensure_headers(sheet)
    return sheet


def ensure_headers(sheet):
    existing = sheet.row_values(1)
    headers = [
        "Date/Time",
        "Meal Name",
        "Calories (kcal)",
        "Protein (g)",
        "Carbs (g)",
        "Fat (g)",
    ]
    if not existing:
        sheet.append_row(headers)


def get_last_logged_date(sheet):
    """Returns the date string (YYYY-MM-DD) of the last logged meal entry."""
    all_values = sheet.get_all_values()
    if len(all_values) <= 1:
        return None

    for row in reversed(all_values):
        if (
            row
            and row[0]
            and not row[0].startswith("---")
            and "TOTAL" not in row[0]
            and "GOAL" not in row[0]
        ):
            return row[0].split(" ")[0]
    return None


def get_totals_for_date(sheet, target_date_str):
    """Sum macros logged on a specific YYYY-MM-DD date."""
    all_rows = sheet.get_all_records()
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    for row in all_rows:
        date_val = str(row.get("Date/Time", ""))
        if date_val.startswith(target_date_str) and "TOTAL" not in date_val:
            try:
                totals["calories"] += float(row.get("Calories (kcal)", 0))
                totals["protein"] += float(row.get("Protein (g)", 0))
                totals["carbs"] += float(row.get("Carbs (g)", 0))
                totals["fat"] += float(row.get("Fat (g)", 0))
            except (ValueError, TypeError):
                continue
    return totals


def handle_day_transition(sheet, profile_limits):
    """Automatically append previous logged day's totals vs goals and a new day header."""
    today_date = datetime.now().strftime("%Y-%m-%d")
    last_date = get_last_logged_date(sheet)

    if last_date and last_date != today_date:
        last_totals = get_totals_for_date(sheet, last_date)

        sheet.append_row(
            [
                f"{last_date} TOTAL",
                "Logged",
                last_totals["calories"],
                last_totals["protein"],
                last_totals["carbs"],
                last_totals["fat"],
            ]
        )
        sheet.append_row(
            [
                f"{last_date} GOAL",
                "Target",
                profile_limits["calories"],
                profile_limits["protein"],
                profile_limits["carbs"],
                profile_limits["fat"],
            ]
        )

        sheet.append_row(["", "", "", "", "", ""])
        sheet.append_row(
            [f"--- {today_date} ---", "---", "---", "---", "---", "---"]
        )


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


def log_meal(sheet, profile_name, profile_limits):
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_totals = get_totals_for_date(sheet, today_str)
    display_dashboard(
        today_totals,
        profile_limits,
        profile_name,
        title="CURRENT DAILY MACRO STATUS",
    )

    print(f"\n--- Enter Meal Details for {profile_name} ---")
    meal_name = (
        input("Meal Name (e.g., Meal 1, Post-workout): ").strip() or "Meal"
    )
    cals = prompt_num("Calories (kcal): ")
    protein = prompt_num("Protein (g): ")
    carbs = prompt_num("Carbs (g): ")
    fat = prompt_num("Fat (g): ")

    handle_day_transition(sheet, profile_limits)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    row_data = [now_str, meal_name, cals, protein, carbs, fat]

    sheet.append_row(row_data)
    print(f"\n✅ Successfully logged '{meal_name}' to {profile_name}'s tab!")

    new_totals = {
        "calories": today_totals["calories"] + cals,
        "protein": today_totals["protein"] + protein,
        "carbs": today_totals["carbs"] + carbs,
        "fat": today_totals["fat"] + fat,
    }
    display_dashboard(
        new_totals,
        profile_limits,
        profile_name,
        title="UPDATED REMAINING BALANCE",
    )


def profile_session(spreadsheet, profile_name, profile_limits):
    """Sub-menu for a specific selected profile session."""
    sheet = get_or_create_worksheet(spreadsheet, profile_name)

    while True:
        print("\n" + "=" * 42)
        print(f"    ACTIVE PROFILE: {profile_name.upper()}    ")
        print("=" * 42)
        print("1. Log a new meal")
        print("2. View today's totals & remaining macros")
        print("3. Exit profile (Return to main menu)")

        choice = input("\nSelect an option (1-3): ").strip()

        if choice == "1":
            log_meal(sheet, profile_name, profile_limits)
        elif choice == "2":
            today_str = datetime.now().strftime("%Y-%m-%d")
            totals = get_totals_for_date(sheet, today_str)
            display_dashboard(totals, profile_limits, profile_name)
        elif choice == "3":
            print(f"\nExited {profile_name}'s session.")
            break
        else:
            print("Invalid choice. Select 1, 2, or 3.")


def main():
    config = load_config()
    print("Connecting to Google Sheets...")
    spreadsheet = connect_sheets(config)

    while True:
        profiles = list(config["profiles"].keys())

        print("\n" + "=" * 42)
        print("      MACRO TRACKER - USER SELECT      ")
        print("=" * 42)
        for idx, p in enumerate(profiles, 1):
            print(f"{idx}. Select Profile: {p}")
        print(f"{len(profiles) + 1}. Exit Script")

        choice = input(f"\nChoose an option (1-{len(profiles) + 1}): ").strip()

        if choice.isdigit():
            c = int(choice)
            if 1 <= c <= len(profiles):
                selected_profile = profiles[c - 1]
                profile_limits = config["profiles"][selected_profile][
                    "daily_limits"
                ]
                profile_session(spreadsheet, selected_profile, profile_limits)
            elif c == len(profiles) + 1:
                print("\nExiting tracker script. Have a great day!\n")
                break
            else:
                print("Invalid choice. Please select from the list.")
        else:
            print("Invalid input. Enter a number.")


if __name__ == "__main__":
    main()