from datetime import datetime
import sys
import gspread


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