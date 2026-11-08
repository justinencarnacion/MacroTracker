"""An in-memory stand-in for the shared Google spreadsheet.

Implements the gspread calls the bot makes (finding and adding tabs, reading
rows, appending, updating, deleting) and raises the same gspread errors, so
sheets/sheet_manager.py and the services above it run unchanged. Each call can
be made slow or fail, like the real API under load or during an outage.

The bot calls Sheets from worker threads (asyncio.to_thread), so all state is
behind a lock, and latency is a real blocking sleep that ties up a thread just
like a slow network call does.
"""

import re
import threading
import time
from collections import deque
from types import SimpleNamespace

from gspread.exceptions import APIError, WorksheetNotFound


def api_error(code):
    """The error gspread raises for an HTTP status code."""
    body = {"error": {"code": code, "message": "fake failure", "status": "UNAVAILABLE"}}
    return APIError(SimpleNamespace(json=lambda: body, text=str(body)))


def _cells(range_name):
    """'B5:F5' -> (first_row, first_col, last_row, last_col), 1-based."""
    match = re.fullmatch(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", range_name)
    if not match:
        raise ValueError(f"Unsupported range {range_name!r}")
    first_col, first_row, last_col, last_row = match.groups()

    def column(letters):
        number = 0
        for letter in letters:
            number = number * 26 + ord(letter) - ord("A") + 1
        return number

    return (int(first_row), column(first_col),
            int(last_row or first_row), column(last_col or first_col))


class FakeSpreadsheet:
    """Pass as `spreadsheet` to MacroBot.

    latency: seconds each API call blocks for.
    """

    title = "MacroTracker (simulated)"

    def __init__(self, latency=0.0):
        self.latency = latency
        self.reads = 0
        self.writes = 0
        self._lock = threading.RLock()
        self._sheets = {}
        self._next_id = 1000
        self._down = None
        self._scripted = deque()

    # --- controls ---------------------------------------------------------

    def outage(self, code=503):
        """Every call fails until restore()."""
        self._down = code

    def restore(self):
        self._down = None
        self._scripted.clear()

    def fail_next(self, times=1, code=503):
        self._scripted.extend([code] * times)

    def rows(self, title):
        """A tab's raw rows (header included), for checking results."""
        with self._lock:
            for sheet in self._sheets.values():
                if sheet.title == title:
                    return [list(row) for row in sheet._rows]
            raise KeyError(f"No tab {title!r}; tabs are {[s.title for s in self._sheets.values()]}")

    # --- gspread Spreadsheet API ------------------------------------------

    def worksheets(self):
        self._call("read")
        with self._lock:
            return list(self._sheets.values())

    def worksheet(self, title):
        self._call("read")
        with self._lock:
            for sheet in self._sheets.values():
                if sheet.title == title:
                    return sheet
        raise WorksheetNotFound(title)

    def get_worksheet_by_id(self, worksheet_id):
        self._call("read")
        with self._lock:
            if worksheet_id in self._sheets:
                return self._sheets[worksheet_id]
        raise WorksheetNotFound(f"id {worksheet_id} not found")

    def add_worksheet(self, title, rows=1000, cols=26):
        self._call("write")
        with self._lock:
            if any(sheet.title == title for sheet in self._sheets.values()):
                raise api_error(400)  # Sheets refuses duplicate tab names
            sheet = FakeWorksheet(self, self._next_id, title)
            self._sheets[sheet.id] = sheet
            self._next_id += 1
            return sheet

    def _call(self, kind):
        """Count the API call, then apply any injected failure and latency."""
        with self._lock:
            if kind == "read":
                self.reads += 1
            else:
                self.writes += 1
            failure = self._scripted.popleft() if self._scripted else self._down
        if self.latency:
            time.sleep(self.latency)
        if failure is not None:
            raise api_error(failure)


class FakeWorksheet:
    def __init__(self, spreadsheet, worksheet_id, title):
        self._spreadsheet = spreadsheet
        self._lock = spreadsheet._lock
        self.id = worksheet_id
        self.title = title
        self._rows = []

    def row_values(self, row):
        self._spreadsheet._call("read")
        with self._lock:
            return list(self._rows[row - 1]) if row <= len(self._rows) else []

    def get_all_values(self):
        self._spreadsheet._call("read")
        with self._lock:
            return [["" if cell is None else str(cell) for cell in row] for row in self._rows]

    def get_all_records(self):
        self._spreadsheet._call("read")
        with self._lock:
            if not self._rows:
                return []
            headers = self._rows[0]
            return [
                {header: row[index] if index < len(row) else ""
                 for index, header in enumerate(headers)}
                for row in self._rows[1:]
            ]

    def append_row(self, values, **options):
        self._spreadsheet._call("write")
        with self._lock:
            self._rows.append(list(values))

    def update(self, values, range_name, **options):
        self._spreadsheet._call("write")
        first_row, first_col, _, _ = _cells(range_name)
        with self._lock:
            for row_offset, new_values in enumerate(values):
                row_index = first_row - 1 + row_offset
                while len(self._rows) <= row_index:
                    self._rows.append([])
                row = self._rows[row_index]
                for col_offset, value in enumerate(new_values):
                    col_index = first_col - 1 + col_offset
                    row.extend([""] * (col_index + 1 - len(row)))
                    row[col_index] = value

    def delete_rows(self, start_index, end_index=None):
        self._spreadsheet._call("write")
        with self._lock:
            del self._rows[start_index - 1:(end_index or start_index)]
