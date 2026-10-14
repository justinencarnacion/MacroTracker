from datetime import date, datetime, timedelta
import logging

import gspread

logger = logging.getLogger(__name__)


class SheetConnectionError(RuntimeError):
    pass


def connect_sheets(credentials_info, sheet_name, sheet_id=None):
    """Open the shared spreadsheet with a service-account credentials dict."""
    try:
        gc = gspread.service_account_from_dict(credentials_info)
        if sheet_id:
            return gc.open_by_key(sheet_id)
        return gc.open(sheet_name)
    except Exception as error:
        raise SheetConnectionError(
            f"Could not open spreadsheet '{sheet_id or sheet_name}': {error}. "
            "Ensure the sheet is shared with the service-account email "
            f"({credentials_info.get('client_email', 'unknown')}) as an Editor."
        ) from error


def worksheet_title(display_name, discord_id):
    """Create a readable, unique Google Sheets worksheet title."""
    safe_name = "".join(
        character for character in display_name if character not in "[]:*?/\\"
    ).strip()
    safe_name = safe_name or "Discord User"
    suffix = f" ({discord_id[-6:]})"
    return f"{safe_name[:100 - len(suffix)]}{suffix}"


def get_or_create_worksheet(spreadsheet, profile_name):
    try:
        sheet = spreadsheet.worksheet(profile_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.info("Creating worksheet tab '%s'", profile_name)
        sheet = spreadsheet.add_worksheet(
            title=profile_name, rows="1000", cols="10"
        )
    ensure_headers(sheet)
    return sheet


def get_worksheet_for_user(spreadsheet, worksheet_id, title):
    """Find a user's tab by its stable ID, falling back to its title.

    Renaming a tab or changing a Discord nickname keeps the same worksheet
    because the ID never changes.
    """
    if worksheet_id is not None:
        try:
            sheet = spreadsheet.get_worksheet_by_id(int(worksheet_id))
            ensure_headers(sheet)
            return sheet
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Worksheet %s not found; recreating '%s'", worksheet_id, title)
    return get_or_create_worksheet(spreadsheet, title)


def find_worksheet_for_user(spreadsheet, worksheet_id, title):
    """Like get_worksheet_for_user, but returns None instead of creating a tab.

    Used for read-only requests, so viewing a summary never creates an empty tab.
    """
    if worksheet_id is not None:
        try:
            return spreadsheet.get_worksheet_by_id(int(worksheet_id))
        except gspread.exceptions.WorksheetNotFound:
            pass
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return None


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


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_meal_row(row):
    timestamp = str(row.get("Date/Time", "")).strip()
    return bool(timestamp) and not any(
        marker in timestamp for marker in ("TOTAL", "GOAL", "---")
    )


def get_meals(sheet, start_date=None, end_date=None):
    """Return meal rows with their worksheet row numbers."""
    records = sheet.get_all_records()
    meals = []
    for row_number, row in enumerate(records, start=2):
        if not _is_meal_row(row):
            continue
        timestamp = str(row.get("Date/Time", ""))
        meal_date = timestamp[:10]
        if start_date and meal_date < str(start_date):
            continue
        if end_date and meal_date > str(end_date):
            continue
        meals.append(
            {
                "row_number": row_number,
                "date_time": timestamp,
                "meal_name": str(row.get("Meal Name", "")),
                "calories": _number(row.get("Calories (kcal)")),
                "protein": _number(row.get("Protein (g)")),
                "carbs": _number(row.get("Carbs (g)")),
                "fat": _number(row.get("Fat (g)")),
            }
        )
    return meals


def get_recent_meals(sheet, limit=10):
    if limit < 1:
        raise ValueError("Meal limit must be positive.")
    meals = sorted(get_meals(sheet), key=lambda meal: meal["date_time"], reverse=True)
    return meals[:limit]


def update_meal(sheet, row_number, meal_name, calories, protein, carbs, fat):
    """Overwrite a meal's name and macros, keeping its original timestamp."""
    if row_number < 2:
        raise ValueError("Meal row number must be at least 2.")
    sheet.update(
        f"B{row_number}:F{row_number}",
        [[
            meal_name,
            calories,
            protein,
            carbs,
            fat,
        ]],
    )


def delete_meal(sheet, row_number):
    if row_number < 2:
        raise ValueError("Meal row number must be at least 2.")
    sheet.delete_rows(row_number)


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
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for meal in get_meals(sheet, target_date_str, target_date_str):
        for key in totals:
            totals[key] += meal[key]
    return totals


def get_weekly_summary(sheet, target_date=None):
    target = target_date or date.today()
    if isinstance(target, str):
        target = date.fromisoformat(target)
    start = target - timedelta(days=6)
    meals = get_meals(sheet, start, target)
    totals = {key: sum(meal[key] for meal in meals) for key in (
        "calories", "protein", "carbs", "fat"
    )}
    by_date = {}
    for meal in meals:
        day = meal["date_time"][:10]
        by_date.setdefault(day, {key: 0.0 for key in totals})
        for key in totals:
            by_date[day][key] += meal[key]
    return {"start_date": str(start), "end_date": str(target), "totals": totals, "by_date": by_date}


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