"""Pure calculations for daily and weekly progress. No I/O."""

from dataclasses import dataclass
from datetime import date, timedelta

from core.macros import MACRO_KEYS


def zero_totals():
    return {key: 0.0 for key in MACRO_KEYS}


def sum_meals(meals):
    totals = zero_totals()
    for meal in meals:
        for key in MACRO_KEYS:
            totals[key] += meal[key]
    return totals


def remaining(goals, totals):
    """Goal minus eaten for each macro; negative means over the goal."""
    return {key: goals[key] - totals[key] for key in MACRO_KEYS}


def week_bounds(day):
    """Monday and Sunday of the calendar week containing `day`."""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def meal_date(meal):
    """The meal's calendar date, or None if its timestamp can't be read."""
    try:
        return date.fromisoformat(str(meal["date_time"])[:10])
    except ValueError:
        return None


@dataclass
class DaySummary:
    day: date
    meals: list  # ordered by time logged; list position + 1 is the meal's number
    totals: dict
    goals: dict
    remaining: dict


@dataclass
class DayTotals:
    day: date
    totals: dict
    meal_count: int
    is_future: bool


@dataclass
class WeekSummary:
    start: date  # Monday
    end: date  # Sunday
    today: date
    days: list  # DayTotals for Monday..Sunday
    totals: dict  # Monday through today
    goals: dict  # daily goals
    days_elapsed: int  # Monday = 1 ... Sunday = 7
    target: dict  # daily goals x days_elapsed
    remaining: dict  # target - totals
    daily_average: dict  # totals / days_elapsed


def summarize_day(meals, day, goals):
    todays = sorted(
        (meal for meal in meals if meal_date(meal) == day),
        key=lambda meal: meal["date_time"],
    )
    totals = sum_meals(todays)
    return DaySummary(
        day=day,
        meals=todays,
        totals=totals,
        goals=dict(goals),
        remaining=remaining(goals, totals),
    )


def summarize_week(meals, today, goals):
    """Monday-Sunday week containing `today`, measured against goal x days so far."""
    start, end = week_bounds(today)
    by_day = {start + timedelta(days=offset): [] for offset in range(7)}
    for meal in meals:
        day = meal_date(meal)
        if day in by_day:
            by_day[day].append(meal)

    days = [
        DayTotals(day=day, totals=sum_meals(day_meals), meal_count=len(day_meals),
                  is_future=day > today)
        for day, day_meals in by_day.items()
    ]
    totals = sum_meals(
        meal for day, day_meals in by_day.items() if day <= today for meal in day_meals
    )
    days_elapsed = (today - start).days + 1
    target = {key: goals[key] * days_elapsed for key in MACRO_KEYS}
    return WeekSummary(
        start=start,
        end=end,
        today=today,
        days=days,
        totals=totals,
        goals=dict(goals),
        days_elapsed=days_elapsed,
        target=target,
        remaining=remaining(target, totals),
        daily_average={key: totals[key] / days_elapsed for key in MACRO_KEYS},
    )
