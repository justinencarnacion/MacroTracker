"""Macro names, display labels, and sanity limits shared across the project."""

MACRO_KEYS = ("calories", "protein", "carbs", "fat")

MACRO_LABELS = {
    "calories": "Calories",
    "protein": "Protein",
    "carbs": "Carbs",
    "fat": "Fat",
}

# Short tags used in compact one-line summaries ("P 35g").
MACRO_TAGS = {"calories": "kcal", "protein": "P", "carbs": "C", "fat": "F"}

# Upper bounds that catch obvious AI mistakes (e.g. 20000 kcal for a sandwich).
MEAL_LIMITS = {"calories": 10000, "protein": 1000, "carbs": 1500, "fat": 1000}
GOAL_LIMITS = {"calories": 20000, "protein": 2000, "carbs": 3000, "fat": 2000}
