from datetime import datetime

import gspread

from sheets.sheet_manager import ensure_headers


def connect_user_spreadsheet(credentials, user, user_store):
    client = gspread.authorize(credentials)
    spreadsheet = (
        client.open_by_key(user["spreadsheet_id"])
        if user["spreadsheet_id"]
        else client.create(f"Macro Tracker - {user['display_name']}")
    )
    if not user["spreadsheet_id"]:
        user_store.set_spreadsheet(user["discord_id"], spreadsheet.id)
    return spreadsheet


def get_current_month_worksheet(spreadsheet):
    title = datetime.now().strftime("%B %Y")
    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="10")
    ensure_headers(worksheet)
    return worksheet
