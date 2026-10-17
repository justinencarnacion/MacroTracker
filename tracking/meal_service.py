"""Listing, editing, and deleting a user's logged meals in their worksheet.

Meals are identified by worksheet row, and rows shift when anything above them
is deleted (by the bot or by hand in the sheet). So every change first
re-reads the sheet and confirms the target row still holds the exact meal the
user picked; if it moved, the meal is found at its new row; if it changed or
is ambiguous, nothing is written.

Methods block on Google Sheets; call them through asyncio.to_thread.
"""

from dataclasses import dataclass
from datetime import timedelta

from core.macros import MACRO_KEYS, MEAL_LIMITS
from sheets.sheet_manager import (
    delete_meal,
    find_worksheet_for_user,
    get_meals,
    update_meal,
    worksheet_title,
)

RECENT_DAYS = 7


class MealChanged(Exception):
    """The meal is no longer where (or what) it was when the user picked it."""

    def __init__(self):
        super().__init__(
            "That meal changed or moved since you opened the list, so nothing "
            "was changed. Run the command again to see the current meals."
        )


class InvalidMeal(ValueError):
    """Edited values that can't be saved."""


@dataclass(frozen=True)
class MealRef:
    """A snapshot of a meal as the user saw it."""

    row_number: int
    date_time: str
    meal_name: str
    calories: float
    protein: float
    carbs: float
    fat: float

    @classmethod
    def from_meal(cls, meal):
        return cls(**{field: meal[field] for field in (
            "row_number", "date_time", "meal_name", *MACRO_KEYS)})

    def same_meal(self, meal):
        return (str(meal["date_time"]) == self.date_time
                and str(meal["meal_name"]) == self.meal_name
                and all(round(float(meal[key]), 2) == round(float(getattr(self, key)), 2)
                        for key in MACRO_KEYS))


def parse_meal_edit(name, values):
    """Validate form input. `values` maps macro -> text; returns clean values."""
    name = (name or "").strip()
    if not name:
        raise InvalidMeal("The meal name can't be empty.")
    if len(name) > 100:
        raise InvalidMeal("The meal name must be 100 characters or fewer.")
    cleaned = {"meal_name": name}
    for key in MACRO_KEYS:
        text = str(values.get(key, "")).strip().replace(",", "")
        try:
            number = float(text) if text else 0.0
        except ValueError:
            raise InvalidMeal(f"{key.capitalize()} must be a number (you entered '{text}').")
        if number < 0 or number > MEAL_LIMITS[key]:
            raise InvalidMeal(f"{key.capitalize()} must be between 0 and {MEAL_LIMITS[key]:,}.")
        cleaned[key] = int(number) if number.is_integer() else round(number, 1)
    if not any(cleaned[key] for key in MACRO_KEYS):
        raise InvalidMeal("At least one of calories, protein, carbs, or fat must be above 0.")
    return cleaned


class MealService:
    def __init__(self, spreadsheet, tracking):
        self.spreadsheet = spreadsheet
        self.tracking = tracking

    def _sheet(self, user):
        return find_worksheet_for_user(
            self.spreadsheet,
            user.get("worksheet_id"),
            worksheet_title(user["display_name"], user["discord_id"]),
        )

    def recent_meals(self, user, days=RECENT_DAYS):
        """Meals from the last `days` days (including today), newest first."""
        today = self.tracking.today_for(user)
        start = today - timedelta(days=days - 1)
        meals = self.tracking.meals_between(user, start, today)
        return sorted(meals, key=lambda meal: meal["date_time"], reverse=True)

    def _locate(self, sheet, ref):
        """The current row number of the meal `ref`, or MealChanged."""
        if sheet is None:
            raise MealChanged()
        meals = get_meals(sheet)
        at_row = next((meal for meal in meals if meal["row_number"] == ref.row_number), None)
        if at_row is not None and ref.same_meal(at_row):
            return ref.row_number
        matches = [meal for meal in meals if ref.same_meal(meal)]
        if len(matches) == 1:  # it moved; identical duplicates are too ambiguous to guess
            return matches[0]["row_number"]
        raise MealChanged()

    def delete(self, user, ref):
        sheet = self._sheet(user)
        delete_meal(sheet, self._locate(sheet, ref))

    def update(self, user, ref, values):
        """`values` comes from parse_meal_edit. The meal keeps its original time."""
        sheet = self._sheet(user)
        update_meal(sheet, self._locate(sheet, ref), values["meal_name"],
                    *(values[key] for key in MACRO_KEYS))
