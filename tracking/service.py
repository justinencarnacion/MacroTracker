from datetime import datetime
from zoneinfo import ZoneInfo

from sheets.sheet_manager import find_worksheet_for_user, get_meals, worksheet_title
from tracking.summaries import summarize_day, summarize_week, week_bounds


class TrackingService:
    """Reads a user's meals from their worksheet and builds summaries.

    Every method reads Google Sheets and blocks; call them through
    asyncio.to_thread. Data is read fresh on every call (no caching), so
    manual edits in the sheet are always reflected.
    """

    def __init__(self, spreadsheet, default_timezone, clock=datetime.now):
        self.spreadsheet = spreadsheet
        self.default_timezone = default_timezone
        self.clock = clock

    def today_for(self, user):
        """The current date in the user's timezone (or the default)."""
        timezone = ZoneInfo(user.get("timezone") or self.default_timezone)
        return self.clock(timezone).date()

    def meals_between(self, user, start, end):
        sheet = find_worksheet_for_user(
            self.spreadsheet,
            user.get("worksheet_id"),
            worksheet_title(user["display_name"], user["discord_id"]),
        )
        if sheet is None:
            return []
        return get_meals(sheet, start, end)

    def day_summary(self, user, goals):
        today = self.today_for(user)
        return summarize_day(self.meals_between(user, today, today), today, goals)

    def week_summary(self, user, goals):
        today = self.today_for(user)
        start, end = week_bounds(today)
        return summarize_week(self.meals_between(user, start, end), today, goals)
