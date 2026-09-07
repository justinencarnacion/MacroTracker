from datetime import datetime
from config_manager import load_config, save_config
from display import display_dashboard, prompt_num
from sheet_manager import (
    connect_sheets,
    get_or_create_worksheet,
    get_totals_for_date,
    handle_day_transition,
)


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


def create_new_profile(spreadsheet, config):
    print("\n--- Create New Profile ---")
    while True:
        name = input("Enter new profile name: ").strip()
        if not name:
            print("Profile name cannot be empty.")
            continue
        if name in config["profiles"]:
            print(f"A profile named '{name}' already exists.")
            return
        break

    print(f"\nSet Daily Limits for {name}:")
    cals = prompt_num("Daily Calories limit (kcal): ")
    protein = prompt_num("Daily Protein limit (g): ")
    carbs = prompt_num("Daily Carbs limit (g): ")
    fat = prompt_num("Daily Fat limit (g): ")

    config["profiles"][name] = {
        "daily_limits": {
            "calories": cals,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
        }
    }

    save_config(config)
    get_or_create_worksheet(spreadsheet, name)
    print(
        f"\n✅ Created profile '{name}' and generated dedicated worksheet tab!"
    )


def main():
    config = load_config()
    print("Connecting to Google Sheets...")
    spreadsheet = connect_sheets(config)

    while True:
        profiles = list(config["profiles"].keys())

        print("\n" + "=" * 42)
        print("      MACRO TRACKER - USER SELECT      ")
        print("=" * 42)

        idx = 1
        for p in profiles:
            print(f"{idx}. Select Profile: {p}")
            idx += 1

        opt_create = idx
        print(f"{opt_create}. Create New Profile")

        opt_exit = idx + 1
        print(f"{opt_exit}. Exit Script")

        choice = input(f"\nChoose an option (1-{opt_exit}): ").strip()

        if choice.isdigit():
            c = int(choice)
            if 1 <= c <= len(profiles):
                selected_profile = profiles[c - 1]
                profile_limits = config["profiles"][selected_profile][
                    "daily_limits"
                ]
                profile_session(spreadsheet, selected_profile, profile_limits)
            elif c == opt_create:
                create_new_profile(spreadsheet, config)
            elif c == opt_exit:
                print("\nExiting tracker script. Have a great day!\n")
                break
            else:
                print("Invalid choice. Please select from the menu.")
        else:
            print("Invalid input. Enter a number.")


if __name__ == "__main__":
    main()
