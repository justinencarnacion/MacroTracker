from core.macros import MACRO_KEYS


class GoalsIncomplete(ValueError):
    """A first-time goal update didn't include all four macros."""

    def __init__(self, missing):
        self.missing = tuple(missing)
        super().__init__(
            "To set your goals for the first time, include all four: calories, "
            f"protein, carbs, and fat (missing: {', '.join(self.missing)})."
        )


def has_goals(goals):
    """True when the user has personally set all four daily goals."""
    return bool(goals) and all(goals.get(key) is not None for key in MACRO_KEYS)


def merge_goals(current, updates):
    """Apply goal updates and return the full set of goals.

    The first time, all four macros are required. After that, any subset can
    change and the rest keep their current values.
    """
    updates = {
        key: value
        for key, value in updates.items()
        if key in MACRO_KEYS and value is not None
    }
    if has_goals(current):
        return {key: updates.get(key, current[key]) for key in MACRO_KEYS}

    missing = [key for key in MACRO_KEYS if key not in updates]
    if missing:
        raise GoalsIncomplete(missing)
    return {key: updates[key] for key in MACRO_KEYS}
